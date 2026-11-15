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

from app.core.permission_guard import require_permission
from app.core.exceptions import ForbiddenError
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyWorkStep
from app.models.module5_estimate_snapshot import EstimatePreviewSnapshot
from app.services.audit_service import log_event
from app.services.module1_offer_qualification import quote_current_offers
from app.services.module1_provider_work_cost_offers import _apply_list_permissions
from app.services.module2_calculation_blocks import _validate_technology_roles, decode_definition, encode_definition
from app.services.module2_fnd3_strip_blocks import (
    CONCRETE_WORK, FORMWORK_WORK, REINFORCEMENT_WORK, TECHNOLOGY_CODE, _strip_blocks,
)
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


async def create_estimate_preview(
    db: AsyncSession, *, actor: object, geometry_revision_id: uuid.UUID | None = None,
    foundation_geometry_revision_id: uuid.UUID | None = None, region: str, terms: str,
    accounting_keys: Mapping[tuple[str, str], str],
    parameter_values: Mapping[tuple[str, str], str] | None = None,
    strip_roles_confirmed: bool = False,
) -> EstimatePreviewSnapshot:
    require_permission(actor, MODULE5_CODE, "CREATE")
    require_permission(actor, MODULE1_CODE, "VIEW")
    if not isinstance(strip_roles_confirmed, bool):
        raise ValueError("strip role confirmation must be boolean")
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
    conflicts = ambiguous_foundation_work_codes(technology.technology_code, tuple(bindings))
    disjoint, missing_roles = await _strip_scope_review(db, technology, blocks, bindings, block_issues,
                                                        strip_roles_confirmed)
    if foundation:
        if geometry.inputs.get("missing"):
            missing_roles += ("Не заполнены обязательные параметры геометрии",)
        if technology.technology_code != TECHNOLOGY_CODE:
            missing_roles += ("Полнота комплектации технологии требует проверки",)
    preview = calculate_statement_preview(tuple(blocks), tuple(bindings), values, quotes,
                                          allow_preliminary_defaults=True, parameter_values=explicit_parameters,
                                          block_issues=block_issues, ambiguous_work_codes=conflicts,
                                          confirmed_disjoint_binding_ids=disjoint)
    if missing_roles:
        preview = replace(preview, complete=False)
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
        "strip_roles_confirmed": strip_roles_confirmed, "missing_required_roles": missing_roles,
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
