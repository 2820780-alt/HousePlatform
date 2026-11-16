"""Create reproducible, owner-scoped preliminary M5 calculations."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict, replace
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permission_guard import require_permission
from app.core.exceptions import ForbiddenError
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.material import Material
from app.models.material_attribute import MaterialAttribute
from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.models.module5_estimate_snapshot import EstimatePreviewSnapshot
from app.services.audit_service import log_event
from app.services.module1_offer_qualification import quote_current_offers
from app.services.module1_material_display import material_ui_attribute_rows
from app.services.module1_provider_work_cost_offers import _apply_list_permissions
from app.services.module2_calculation_blocks import _validate_technology_roles, decode_definition, encode_definition
from app.services.module2_fnd3_strip_blocks import (
    CONCRETE_WORK, FORMWORK_WORK, REINFORCEMENT_WORK, TECHNOLOGY_CODE, _strip_blocks,
)
from app.services.module2_fnd3_slab_blocks import (REBAR_ROLES as SLAB_REBAR_ROLES,
    REBAR_WORK as SLAB_REBAR_WORK, TECHNOLOGY_CODE as SLAB_TECHNOLOGY_CODE, reinforcement_block as slab_rebar_block)
from app.services.module2_fnd3_bored_pile_blocks import (REBAR_ROLES as PILE_REBAR_ROLES,
    REBAR_WORK as PILE_REBAR_WORK, TECHNOLOGY_CODE as PILE_TECHNOLOGY_CODE, reinforcement_block as pile_rebar_block)
from app.services.module2_fnd3_driven_pile_blocks import (TECHNOLOGY_CODE as DRIVEN_PILE_CODE,
    expected_blocks as expected_driven_pile_blocks)
from app.services.module2_fnd3_screw_pile_blocks import (TECHNOLOGY_CODE as SCREW_PILE_CODE,
    expected_blocks as expected_screw_pile_blocks)
from app.services.module2_fnd3_membrane_blocks import (TECHNOLOGY_CODE as MEMBRANE_CODE,
    expected_blocks as expected_membrane_blocks)
from app.services.module2_fnd3_ribbed_slab_blocks import (TECHNOLOGY_CODE as RIBBED_SLAB_CODE,
    USHP_CODE, REBAR_ROLES as RIBBED_REBAR_ROLES, REBAR_WORK as RIBBED_REBAR_WORK,
    reinforcement_block as ribbed_rebar_block, expected_blocks as expected_ribbed_slab_blocks)
from app.services.module2_fnd3_column_wall_blocks import (REBAR_ROLES as COLUMN_WALL_REBAR_ROLES,
    REBAR_WORK as COLUMN_WALL_REBAR_WORK, reinforcement_block as column_wall_rebar_block)
from app.services.module2_fnd3_uff_blocks import (TECHNOLOGY_CODE as UFF_CODE,
    concrete_blocks as uff_concrete_blocks, expected_blocks as expected_uff_roles)
from app.services.module2_fnd3_grillage_blocks import (TECHNOLOGY_CODE as GRILLAGE_CODE,
    expected_blocks as expected_grillage_blocks)
from app.services.module5_calculation_preview import (
    PROTECTED_GEOMETRY_INPUTS, StatementBinding, ambiguous_foundation_work_codes, calculate_statement_preview,
)
from app.services.module7_strip_geometry import read_strip_geometry
from app.services.module7_foundation_geometry import read_foundation_geometry
from app.services.module7_foundation_inputs import FOUNDATION_FIELDS

MODULE5_CODE = "MODULE_05_ESTIMATE_ENGINE"
MODULE1_CODE = "MODULE_01_MATERIAL_HUB"
FOUNDATION_INPUT_ALIASES = {"geometry.slab_thickness": "technology.slab_thickness"}


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str, sort_keys=True))


async def _strip_scope_review(db, technology, blocks, bindings, block_issues, confirmed):
    if technology.technology_code != TECHNOLOGY_CODE:
        return frozenset(), ()
    role_codes = {"FND2_BT_02", "REBAR_TOP", "REBAR_BOTTOM", "STIRRUPS", "FND2_FORM_01"}
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(role_codes)))).all()}
    work_codes = {CONCRETE_WORK, FORMWORK_WORK, REINFORCEMENT_WORK}
    step_rows = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code.in_(work_codes)))).all()
    steps = {row.work_code: row for row in step_rows}
    if (set(roles) != role_codes or any(role.canonical_material_id is None for role in roles.values()) or
            len(step_rows) != 3 or set(steps) != work_codes):
        return frozenset(), ("Связи основных ролей ленты требуют проверки",)
    expected = {item.id: item for item in _strip_blocks(technology.id, roles, steps)}
    actual = {item.id: item for item in blocks}
    missing = tuple(item.name for key, item in expected.items()
                    if key not in actual or key in block_issues or
                    not actual[key].material_id or not actual[key].material_output_id or
                    not actual[key].work_code or not actual[key].work_output_id)
    # The configured core does not yet model all project-specific preparation,
    # protection and auxiliary work choices of the existing technology.
    missing += ("Состав вспомогательных материалов и работ",)
    if not confirmed:
        return frozenset(), missing
    exact = {key for key, item in actual.items() if key in expected and key not in block_issues and
             encode_definition(item) == encode_definition(expected[key]) and
             item.material_id == expected[key].material_id and item.work_code == expected[key].work_code}
    role_by_id = {str(role.id): code for code, role in roles.items()}
    allowed = set()
    for kind in ("MATERIAL", "WORK"):
        groups = {}
        for binding in bindings:
            if binding.kind == kind and binding.resource_id:
                groups.setdefault(binding.resource_id, []).append(binding)
        for resource, group in groups.items():
            if len(group) < 2 or any(item.block_id not in exact for item in group):
                continue
            names = [role_by_id.get(actual[item.block_id].material_requirement_id) for item in group]
            accepted = {"REBAR_TOP", "REBAR_BOTTOM"} if kind == "MATERIAL" else {"REBAR_TOP", "REBAR_BOTTOM", "STIRRUPS"}
            if (len(set(names)) == len(names) and set(names) <= accepted and
                    (kind == "MATERIAL" or resource == REINFORCEMENT_WORK)):
                allowed.update(item.id for item in group)
    return frozenset(allowed), missing


async def _reinforcement_scope_review(db, technology, blocks, bindings, block_issues, confirmed,
                                      technology_code, role_codes, work_code, make_block):
    if technology.technology_code != technology_code or not confirmed:
        return frozenset()
    roles = {row.code: row for row in (await db.scalars(select(TechnologyMaterialRequirement).where(
        TechnologyMaterialRequirement.technology_id == technology.id,
        TechnologyMaterialRequirement.code.in_(role_codes)))).all()}
    steps = (await db.scalars(select(TechnologyWorkStep).where(
        TechnologyWorkStep.technology_id == technology.id, TechnologyWorkStep.work_code == work_code))).all()
    if set(roles) != set(role_codes) or any(role.canonical_material_id is None for role in roles.values()) or len(steps) != 1:
        return frozenset()
    expected = {block.id: block for block in (make_block(technology.id, code, roles[code], steps[0])
                                               for code in role_codes)}
    actual = {block.id: block for block in blocks}
    exact = {key for key, item in actual.items() if key in expected and key not in block_issues and
             encode_definition(item) == encode_definition(expected[key]) and
             item.material_id == expected[key].material_id and item.work_code == expected[key].work_code}
    role_by_id = {str(role.id): code for code, role in roles.items()}
    allowed = set()
    for kind in ("MATERIAL", "WORK"):
        groups = {}
        for binding in bindings:
            if binding.kind == kind and binding.resource_id:
                groups.setdefault(binding.resource_id, []).append(binding)
        for resource, group in groups.items():
            if len(group) < 2 or any(item.block_id not in exact for item in group):
                continue
            names = [role_by_id.get(actual[item.block_id].material_requirement_id) for item in group]
            if (len(set(names)) == len(names) and set(names) <= set(role_codes) and
                    (kind == "MATERIAL" or resource == work_code)):
                allowed.update(item.id for item in group)
    return frozenset(allowed)


async def _ribbed_scope_review(db, technology, blocks, bindings, block_issues, confirmed):
    if technology.technology_code not in {RIBBED_SLAB_CODE, USHP_CODE} or not confirmed:
        return frozenset()
    try:
        expected = {item.id: item for item in await expected_ribbed_slab_blocks(db, technology)}
    except ValueError:
        return frozenset()
    actual = {item.id: item for item in blocks}
    exact = {key for key, item in actual.items() if key in expected and key not in block_issues and
             encode_definition(item) == encode_definition(expected[key]) and
             item.material_id == expected[key].material_id and item.work_code == expected[key].work_code}
    allowed = set()
    for kind in ("MATERIAL", "WORK"):
        groups = {}
        for binding in bindings:
            if binding.kind == kind and binding.resource_id:
                groups.setdefault(binding.resource_id, []).append(binding)
        for group in groups.values():
            if (len(group) == 2 and {item.block_id for item in group} == set(expected) and
                    all(item.block_id in exact for item in group) and
                    len({actual[item.block_id].material_requirement_id for item in group}) == 2):
                allowed.update(item.id for item in group)
    return frozenset(allowed)


async def create_estimate_preview(
    db: AsyncSession, *, actor: object, geometry_revision_id: uuid.UUID | None = None,
    foundation_geometry_revision_id: uuid.UUID | None = None, region: str, terms: str,
    accounting_keys: Mapping[tuple[str, str], str],
    parameter_values: Mapping[tuple[str, str], str] | None = None,
    strip_roles_confirmed: bool = False,
    slab_roles_confirmed: bool = False,
    pile_roles_confirmed: bool = False,
    screw_head_match_confirmed: bool = False,
    membrane_areas_disjoint_confirmed: bool = False,
    ribbed_concrete_disjoint_confirmed: bool = False,
    column_wall_rebar_disjoint_confirmed: bool = False,
    uff_floor_disjoint_confirmed: bool = False,
    grillage_rebar_disjoint_confirmed: bool = False,
    grillage_bundle_scope_confirmed: bool = False,
    ribbed_rebar_disjoint_confirmed: bool = False,
) -> EstimatePreviewSnapshot:
    require_permission(actor, MODULE5_CODE, "CREATE")
    require_permission(actor, MODULE1_CODE, "VIEW")
    if not all(isinstance(value, bool) for value in (strip_roles_confirmed, slab_roles_confirmed,
            pile_roles_confirmed, screw_head_match_confirmed, membrane_areas_disjoint_confirmed,
            ribbed_concrete_disjoint_confirmed, column_wall_rebar_disjoint_confirmed,
            uff_floor_disjoint_confirmed, grillage_rebar_disjoint_confirmed, grillage_bundle_scope_confirmed,
            ribbed_rebar_disjoint_confirmed)):
        raise ValueError("role confirmation must be boolean")
    if not region.strip() or not terms.strip():
        raise ValueError("region and price conditions are required")
    if (geometry_revision_id is None) == (foundation_geometry_revision_id is None):
        raise ValueError("exactly one geometry revision is required")
    foundation = foundation_geometry_revision_id is not None
    geometry = (await read_foundation_geometry(db, actor=actor, revision_id=foundation_geometry_revision_id)
                if foundation else await read_strip_geometry(db, actor=actor, revision_id=geometry_revision_id))
    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == geometry.technology_id).order_by(
        TechnologyCalculationBlock.position))).all()
    quote_date = date.today()
    blocks, bindings, quotes, quote_errors, block_issues = [], [], {}, {}, {}
    for row in rows:
        block = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                  material_id=str(row.material_id) if row.material_id else None, work_code=row.work_code)
        blocks.append(block)
        try:
            await _validate_technology_roles(db, geometry.technology_id, block)
        except ValueError:
            block_issues[block.id] = ("TECHNOLOGY_ROLE_INVALID",)
        for kind, resource, output in (("MATERIAL", block.material_id, block.material_output_id),
                                       ("WORK", block.work_code, block.work_output_id)):
            if output is None:
                continue
            scope = (accounting_keys.get((block.id, kind)) or "").strip()
            if not scope or len(scope) > 255:
                raise ValueError("each material and work output requires an explicit accounting key")
            role_id = block.material_requirement_id if kind == "MATERIAL" else block.work_step_id
            bindings.append(StatementBinding(f"{block.id}:{kind}", block.id, kind, resource, output, scope, role_id))
            if resource and (kind, resource) not in quotes:
                try:
                    quotes[(kind, resource)] = await quote_current_offers(
                        db, material_id=uuid.UUID(resource) if kind == "MATERIAL" else None,
                        work_code=resource if kind == "WORK" else None,
                        region=region, terms=terms, as_of=quote_date, actor=actor)
                except ValueError:
                    quote_errors[f"{kind}:{resource}"] = "PRICE_CONTEXT_OR_RESOURCE_INVALID"
    if foundation:
        values = {key: (Decimal(item["value"]), item["unit"]) for key, item in geometry.inputs["values"].items()}
        protected = set(PROTECTED_GEOMETRY_INPUTS) | {
            item.key for item in FOUNDATION_FIELDS[geometry.inputs["technology_code"]]}
        for source, target in FOUNDATION_INPUT_ALIASES.items():
            if source in protected:
                protected.add(target)
                if source in values:
                    values[target] = values[source]
    else:
        values = {"geometry.length": (geometry.length_m, "m"), "geometry.width": (geometry.width_m, "m"),
                  "geometry.height": (geometry.height_m, "m")}
        protected = PROTECTED_GEOMETRY_INPUTS
    allowed_parameters = {(block.id, item.input_key): item for block in blocks for item in block.parameters}
    submitted = parameter_values or {}
    if set(submitted) - set(allowed_parameters) or any(key in protected for _, key in submitted):
        raise ValueError("unknown calculation parameter")
    explicit_parameters = {}
    for key, raw in submitted.items():
        if not isinstance(raw, str) or len(raw) > 80:
            raise ValueError("invalid calculation parameter")
        try:
            value = Decimal(raw.strip().replace(",", "."))
        except InvalidOperation:
            raise ValueError("invalid calculation parameter") from None
        if not value.is_finite() or value.adjusted() > 24 or value.adjusted() < -24:
            raise ValueError("invalid calculation parameter")
        explicit_parameters[key] = (value, allowed_parameters[key].unit)
    technology = await db.get(Technology, geometry.technology_id)
    if technology is None:
        raise ValueError("technology revision no longer exists")
    if foundation and technology.technology_code == DRIVEN_PILE_CODE:
        valid_allocation = False
        try:
            expected = await expected_driven_pile_blocks(db, technology)
            actual = {block.id: block for block in blocks}
            exact = all(item.id in actual and item.id not in block_issues and
                        encode_definition(actual[item.id]) == encode_definition(item) and
                        actual[item.id].material_id == item.material_id and actual[item.id].work_code == item.work_code
                        for item in expected)
            counts = [explicit_parameters.get((item.id, item.parameters[0].input_key)) for item in expected[:2]]
            total = values.get("pile.count")
            valid_allocation = bool(exact and total and all(item is not None for item in counts) and
                all(item[0] >= 0 and item[0] == item[0].to_integral_value() for item in counts) and
                sum(item[0] for item in counts) == total[0])
        except ValueError:
            valid_allocation = False
        if not valid_allocation:
            for block in blocks:
                block_issues[block.id] = (*block_issues.get(block.id, ()), "PILE_ALLOCATION_UNVERIFIED")
    if foundation and technology.technology_code == SCREW_PILE_CODE:
        screw_valid = False
        try:
            expected = await expected_screw_pile_blocks(db, technology)
            actual = {block.id: block for block in blocks}
            exact = all(item.id in actual and item.id not in block_issues and
                        encode_definition(actual[item.id]) == encode_definition(item) and
                        actual[item.id].material_id == item.material_id and actual[item.id].work_code == item.work_code
                        for item in expected)
            counts = [explicit_parameters.get((item.id, item.parameters[0].input_key)) for item in expected[:5]]
            pile_total, head_total = values.get("pile.count"), values.get("pile.head_count")
            screw_valid = bool(exact and pile_total and head_total and all(item is not None for item in counts) and
                all(item[0] >= 0 and item[0] == item[0].to_integral_value() for item in counts) and
                sum(item[0] for item in counts[:3]) == pile_total[0] and
                sum(item[0] for item in counts[3:]) == head_total[0] and head_total[0] <= pile_total[0] and
                (head_total[0] == 0 or screw_head_match_confirmed))
        except ValueError:
            screw_valid = False
        if not screw_valid:
            for block in blocks:
                block_issues[block.id] = (*block_issues.get(block.id, ()), "PILE_ALLOCATION_UNVERIFIED")
    if foundation and technology.technology_code == MEMBRANE_CODE:
        membrane_valid = False
        try:
            expected = await expected_membrane_blocks(db, technology)
            actual = {block.id: block for block in blocks}
            exact = all(item.id in actual and item.id not in block_issues and
                        encode_definition(actual[item.id]) == encode_definition(item) and
                        actual[item.id].material_id == item.material_id and actual[item.id].work_code == item.work_code
                        for item in expected)
            areas = [explicit_parameters.get((item.id, item.parameters[0].input_key)) for item in expected[:2]]
            laps = [explicit_parameters.get((item.id, item.parameters[1].input_key)) for item in expected[:2]]
            total = values.get("geometry.area")
            membrane_valid = bool(exact and total and all(item is not None and item[0] >= 0 for item in areas) and
                sum(item[0] for item in areas) == total[0] and
                all(area[0] > 0 or lap is None or lap[0] == 0 for area, lap in zip(areas, laps)) and
                (sum(area[0] > 0 for area in areas) <= 1 or membrane_areas_disjoint_confirmed))
        except ValueError:
            membrane_valid = False
        if not membrane_valid:
            for block in blocks:
                block_issues[block.id] = (*block_issues.get(block.id, ()), "COVERAGE_ALLOCATION_UNVERIFIED")
    if foundation and technology.technology_code == UFF_CODE:
        uff_scope_valid = False
        try:
            roles, steps = await expected_uff_roles(db, technology)
            expected = uff_concrete_blocks(technology.id, roles, steps)
            actual = {block.id: block for block in blocks}
            uff_scope_valid = bool(uff_floor_disjoint_confirmed and all(
                item.id in actual and item.id not in block_issues and
                encode_definition(actual[item.id]) == encode_definition(item) and
                actual[item.id].material_id == item.material_id and actual[item.id].work_code == item.work_code
                for item in expected))
            protected_ids = {item.id for item in expected}
        except ValueError:
            protected_ids = {block.id for block in blocks}
        if not uff_scope_valid:
            for block in blocks:
                if block.id in protected_ids:
                    block_issues[block.id] = (*block_issues.get(block.id, ()), "UFF_SCOPE_UNVERIFIED")
    grillage_exact, grillage_expected, grillage_allocation_valid = False, (), False
    if foundation and technology.technology_code == GRILLAGE_CODE:
        try:
            grillage_expected = await expected_grillage_blocks(db, technology)
            actual = {block.id: block for block in blocks}
            grillage_exact = all(item.id in actual and item.id not in block_issues and
                encode_definition(actual[item.id]) == encode_definition(item) and
                actual[item.id].material_id == item.material_id and actual[item.id].work_code == item.work_code
                for item in grillage_expected)
            counts = [explicit_parameters.get((item.id, item.parameters[0].input_key)) for item in grillage_expected[:5]]
            total = values.get("pile.count")
            grillage_allocation_valid = bool(grillage_exact and total and all(item is not None for item in counts) and
                all(item[0] >= 0 and item[0] == item[0].to_integral_value() for item in counts) and
                sum(item[0] for item in counts) == total[0])
        except ValueError:
            pass
        if not grillage_allocation_valid:
            for block in blocks:
                block_issues[block.id] = (*block_issues.get(block.id, ()), "PILE_ALLOCATION_UNVERIFIED")
        if not (grillage_exact and grillage_bundle_scope_confirmed):
            bundled_ids = {item.id for item in grillage_expected if item.work_code} if grillage_expected else {
                item.id for item in blocks if item.work_code}
            for block in blocks:
                if block.id in bundled_ids:
                    block_issues[block.id] = (*block_issues.get(block.id, ()), "BUNDLE_SCOPE_UNVERIFIED")
    conflicts = ambiguous_foundation_work_codes(technology.technology_code, tuple(bindings))
    disjoint, missing_roles = await _strip_scope_review(db, technology, blocks, bindings, block_issues,
                                                        strip_roles_confirmed)
    disjoint |= await _reinforcement_scope_review(db, technology, blocks, bindings, block_issues, slab_roles_confirmed,
        SLAB_TECHNOLOGY_CODE, SLAB_REBAR_ROLES, SLAB_REBAR_WORK, slab_rebar_block)
    disjoint |= await _reinforcement_scope_review(db, technology, blocks, bindings, block_issues, pile_roles_confirmed,
        PILE_TECHNOLOGY_CODE, PILE_REBAR_ROLES, PILE_REBAR_WORK, pile_rebar_block)
    disjoint |= await _reinforcement_scope_review(db, technology, blocks, bindings, block_issues,
        ribbed_rebar_disjoint_confirmed, RIBBED_SLAB_CODE, RIBBED_REBAR_ROLES, RIBBED_REBAR_WORK, ribbed_rebar_block)
    disjoint |= await _ribbed_scope_review(db, technology, blocks, bindings, block_issues, ribbed_concrete_disjoint_confirmed)
    if technology.technology_code in COLUMN_WALL_REBAR_ROLES:
        disjoint |= await _reinforcement_scope_review(db, technology, blocks, bindings, block_issues,
            column_wall_rebar_disjoint_confirmed, technology.technology_code,
            COLUMN_WALL_REBAR_ROLES[technology.technology_code], COLUMN_WALL_REBAR_WORK,
            lambda tech_id, code, role, step: column_wall_rebar_block(tech_id, technology.technology_code, code, role, step))
    if grillage_exact and grillage_rebar_disjoint_confirmed:
        expected_rebar = {item.id: item for item in grillage_expected[5:8]}
        for resource in {item.resource_id for item in bindings if item.kind == "MATERIAL" and item.resource_id}:
            group = [item for item in bindings if item.kind == "MATERIAL" and item.resource_id == resource]
            if (len(group) > 1 and all(item.block_id in expected_rebar and item.block_id not in block_issues for item in group)
                    and len({expected_rebar[item.block_id].material_requirement_id for item in group}) == len(group)):
                disjoint |= frozenset(item.id for item in group)
    if foundation:
        if geometry.inputs.get("missing"):
            missing_roles += ("Не заполнены обязательные параметры геометрии",)
        if technology.technology_code != TECHNOLOGY_CODE:
            missing_roles += ("Полнота комплектации технологии требует проверки",)
        if technology.technology_code == USHP_CODE and values.get("geometry.wall_area", (Decimal(0), "m2"))[0] > 0:
            missing_roles += ("Материал утепления стен не выбран",)
        if technology.technology_code == UFF_CODE:
            if not uff_scope_valid:
                missing_roles += ("Подтвердите, что площадь пола не включает фундаментную часть",)
            if values.get("geometry.wall_area", (Decimal(0), "m2"))[0] > 0 or values.get("geometry.edge_area", (Decimal(0), "m2"))[0] > 0:
                missing_roles += ("Материал утепления стен или торцов не выбран",)
        if technology.technology_code == GRILLAGE_CODE:
            if not grillage_allocation_valid:
                missing_roles += ("Проверьте распределение свай по исполнениям",)
            if not (grillage_exact and grillage_bundle_scope_confirmed):
                missing_roles += ("Проверьте состав комплексной работы и отсутствие повторного учёта",)
        if technology.technology_code == DRIVEN_PILE_CODE and not valid_allocation:
            missing_roles += ("Распределение количества свай по исполнениям не подтверждено",)
        if technology.technology_code == SCREW_PILE_CODE and not screw_valid:
            missing_roles += ("Проверьте распределение свай и оголовков и подтвердите их совместимость",)
        if technology.technology_code == MEMBRANE_CODE and not membrane_valid:
            missing_roles += ("Проверьте распределение площади между материалами и отсутствие пересечений",)
    preview = calculate_statement_preview(tuple(blocks), tuple(bindings), values, quotes,
                                          allow_preliminary_defaults=True, parameter_values=explicit_parameters,
                                          block_issues=block_issues, ambiguous_work_codes=conflicts,
                                          confirmed_disjoint_binding_ids=disjoint)
    if missing_roles:
        preview = replace(preview, complete=False)
    material_ids = {uuid.UUID(item.resource_id) for item in bindings if item.kind == "MATERIAL" and item.resource_id}
    work_codes = {item.resource_id for item in bindings if item.kind == "WORK" and item.resource_id}
    materials = (await db.scalars(select(Material).where(Material.id.in_(material_ids)).options(
        selectinload(Material.attributes).selectinload(MaterialAttribute.unit)))).all()
    work_rows = (await db.execute(select(WorkCatalogItem.work_code, WorkCatalogItem.work_name).where(
        WorkCatalogItem.work_code.in_(work_codes)))).all()
    resource_names = {f"MATERIAL:{material.id}": material.canonical_name for material in materials}
    resource_names.update({f"WORK:{code}": name for code, name in work_rows})
    resource_characteristics = {str(material.id): sorted(material_ui_attribute_rows(material),
        key=lambda item: (item["label"], item["value"], item["unit"])) for material in materials}
    graph = _json([asdict(block) for block in blocks])
    graph_hash = hashlib.sha256(json.dumps(graph, ensure_ascii=True, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
    geometry_payload = {"revision_id": geometry.id, "version": geometry.version,
                        "technology_id": geometry.technology_id}
    if foundation:
        geometry_payload.update({"kind": "FOUNDATION", "inputs": geometry.inputs})
    else:
        geometry_payload.update({"length_m": geometry.length_m, "width_m": geometry.width_m,
                                 "height_m": geometry.height_m})
    payload = _json({"schema_version": 1, "mode": "PREVIEW", "geometry": geometry_payload,
        "region": region, "terms": terms, "graph": graph, "graph_hash": graph_hash,
        "parameters": [{"block_id": key[0], "input_key": key[1], "value": value[0], "unit": value[1]}
                       for key, value in explicit_parameters.items()],
        "strip_roles_confirmed": strip_roles_confirmed, "slab_roles_confirmed": slab_roles_confirmed,
        "pile_roles_confirmed": pile_roles_confirmed,
        "screw_head_match_confirmed": screw_head_match_confirmed,
        "membrane_areas_disjoint_confirmed": membrane_areas_disjoint_confirmed,
        "ribbed_concrete_disjoint_confirmed": ribbed_concrete_disjoint_confirmed,
        "column_wall_rebar_disjoint_confirmed": column_wall_rebar_disjoint_confirmed,
        "uff_floor_disjoint_confirmed": uff_floor_disjoint_confirmed,
        "grillage_rebar_disjoint_confirmed": grillage_rebar_disjoint_confirmed,
        "grillage_bundle_scope_confirmed": grillage_bundle_scope_confirmed,
        "ribbed_rebar_disjoint_confirmed": ribbed_rebar_disjoint_confirmed,
        "missing_required_roles": missing_roles, "resource_names": resource_names,
        "resource_characteristics": resource_characteristics,
        "quotes": [{"kind": key[0], "resource_id": key[1], "quote": asdict(quote)}
                   for key, quote in quotes.items()], "quote_errors": quote_errors, "result": asdict(preview)})
    snapshot = EstimatePreviewSnapshot(id=uuid.uuid4(), owner_user_id=getattr(actor, "id"),
                                       geometry_revision_id=None if foundation else geometry.id,
                                       foundation_geometry_revision_id=geometry.id if foundation else None,
                                       mode="PREVIEW", payload=payload)
    db.add(snapshot)
    await db.flush()
    await log_event(db, "M5_PREVIEW_CREATED", "EstimatePreviewSnapshot", snapshot.id, getattr(actor, "id"),
                    {"geometry_revision_id": str(geometry.id), "complete": preview.complete})
    return snapshot


async def read_estimate_preview(db: AsyncSession, *, actor: object, snapshot_id: uuid.UUID) -> EstimatePreviewSnapshot:
    require_permission(actor, MODULE5_CODE, "VIEW")
    require_permission(actor, MODULE1_CODE, "VIEW")
    snapshot = await db.scalar(select(EstimatePreviewSnapshot).where(
        EstimatePreviewSnapshot.id == snapshot_id, EstimatePreviewSnapshot.owner_user_id == getattr(actor, "id", None)))
    if snapshot is None:
        raise ValueError("estimate preview not found")
    if snapshot.foundation_geometry_revision_id:
        await read_foundation_geometry(db, actor=actor, revision_id=snapshot.foundation_geometry_revision_id)
    else:
        await read_strip_geometry(db, actor=actor, revision_id=snapshot.geometry_revision_id)
    work_offer_ids = set()
    for entry in snapshot.payload.get("quotes", []):
        if entry.get("kind") == "WORK":
            quote = entry.get("quote", {})
            work_offer_ids.update(item["offer_id"] for item in quote.get("contributors", []))
            work_offer_ids.update(item[0] for item in quote.get("excluded", []))
    if work_offer_ids:
        query = _apply_list_permissions(select(ProviderWorkCostOffer.id).where(
            ProviderWorkCostOffer.id.in_([uuid.UUID(item) for item in work_offer_ids])), actor, owner_user_id=None)
        visible = {str(item) for item in (await db.scalars(query)).all()}
        if visible != work_offer_ids:
            raise ForbiddenError("Work offer access is required to view this calculation")
    return snapshot
