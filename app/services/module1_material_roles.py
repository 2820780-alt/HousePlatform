from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_extraction_blueprint_registry import ExtractionBlueprintRegistry
from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)
from app.services.module1_technical_profile_packaging import MaterialTechnicalProfile


VALID_ROLE_PRIORITIES = frozenset({"primary", "secondary", "conditional"})

GROUP_DEFAULT_ROLE_FIELDS: Mapping[str, tuple[str, ...]] = {
    "aerated_concrete_block": ("length_mm", "width_mm", "height_mm", "density_class", "strength_class"),
    "board": ("thickness_mm", "width_mm", "length_mm"),
    "deep_penetration_primer": ("consumption_l_m2", "primer_type", "compatible_substrates"),
    "flexible_shingle": ("coverage_area_per_pack_m2", "min_roof_slope_deg"),
    "gypsum_board_moisture_resistant": ("length_mm", "width_mm", "thickness_mm", "board_type"),
    "metal_tile": ("profile_name", "effective_width_mm", "coating"),
    "mineral_wool_slab": ("thickness_mm", "area_per_pack_m2", "application"),
    "ready_mix_concrete": ("concrete_class", "unit", "application"),
    "rebar": ("diameter_mm", "steel_class", "kg_per_meter"),
    "xps_board": ("thickness_mm", "area_per_pack_m2", "application"),
}

ROLE_METADATA: Mapping[str, Mapping[str, Any]] = {
    "absorbent_substrate_primer": {
        "usage_context": "substrate_preparation",
        "priority": "secondary",
        "recommended_fields": ("drying_time",),
    },
    "auxiliary_lumber": {"usage_context": "temporary_auxiliary_structures", "priority": "secondary"},
    "blind_area_concrete": {"usage_context": "blind_area", "priority": "secondary"},
    "blind_area_insulation": {"usage_context": "blind_area", "priority": "secondary"},
    "bond_beam_concrete": {"usage_context": "masonry_reinforcement", "priority": "secondary"},
    "bond_beam_reinforcement": {"usage_context": "masonry_reinforcement", "priority": "secondary"},
    "ceiling_sheathing": {"usage_context": "ceiling", "priority": "secondary"},
    "concrete_path": {"usage_context": "site_improvement", "priority": "secondary"},
    "facade_insulation": {"usage_context": "facade", "priority": "primary"},
    "fence_post_concrete": {"usage_context": "fence", "priority": "secondary"},
    "fence_structure": {"usage_context": "fence", "priority": "secondary"},
    "floor_insulation": {"usage_context": "floor", "priority": "secondary"},
    "formwork_board": {"usage_context": "formwork", "priority": "primary"},
    "foundation_insulation": {"usage_context": "foundation", "priority": "primary"},
    "foundation_reinforcement": {"usage_context": "foundation", "priority": "primary"},
    "inner_wall_block": {"usage_context": "inner_walls", "priority": "secondary"},
    "lintel_concrete": {"usage_context": "lintel", "priority": "secondary"},
    "lintel_reinforcement": {"usage_context": "lintel", "priority": "secondary"},
    "mansard_roof_covering": {"usage_context": "roof", "priority": "conditional", "recommended_fields": ("coating",)},
    "masonry_reinforcement": {"usage_context": "masonry", "priority": "secondary"},
    "outer_wall_block": {"usage_context": "outer_walls", "priority": "primary"},
    "partition_block": {"usage_context": "partitions", "priority": "secondary"},
    "partition_sheathing": {"usage_context": "partitions", "priority": "secondary"},
    "partition_sound_insulation": {"usage_context": "partitions", "priority": "secondary"},
    "pile_concrete": {"usage_context": "foundation", "priority": "secondary"},
    "plaster_substrate_primer": {"usage_context": "substrate_preparation", "priority": "primary"},
    "plinth_insulation": {"usage_context": "plinth", "priority": "secondary"},
    "porch_concrete": {"usage_context": "porch", "priority": "secondary"},
    "requires_solid_base": {
        "usage_context": "roof",
        "priority": "conditional",
        "conditions": ("requires_solid_base",),
        "warnings": ("Requires solid base selection outside Module 1.",),
    },
    "requires_underlayment": {
        "usage_context": "roof",
        "priority": "conditional",
        "conditions": ("requires_underlayment",),
        "warnings": ("Requires underlayment selection outside Module 1.",),
    },
    "roof_batten": {"usage_context": "roof", "priority": "secondary"},
    "roof_covering": {"usage_context": "roof", "priority": "primary", "recommended_fields": ("coating",)},
    "roof_insulation": {"usage_context": "roof", "priority": "secondary"},
    "slab_foundation_concrete": {"usage_context": "foundation", "priority": "primary"},
    "slab_reinforcement": {"usage_context": "slab", "priority": "secondary"},
    "strip_foundation_concrete": {"usage_context": "foundation", "priority": "primary"},
    "temporary_flooring": {"usage_context": "temporary_auxiliary_structures", "priority": "secondary"},
    "tile_substrate_primer": {"usage_context": "substrate_preparation", "priority": "secondary"},
    "wall_lining": {"usage_context": "wall_lining", "priority": "primary"},
    "wet_room_sheathing": {
        "usage_context": "wet_rooms",
        "priority": "conditional",
        "conditions": ("board_type must be moisture resistant",),
    },
}

GROUP_ROLE_FIELD_OVERRIDES: Mapping[tuple[str, str], tuple[str, ...]] = {
    ("gypsum_board_moisture_resistant", "wet_room_sheathing"): (
        "length_mm",
        "width_mm",
        "thickness_mm",
        "board_type",
        "sheet_area_m2",
    ),
    ("metal_tile", "roof_covering"): ("profile_name", "effective_width_mm", "coating"),
    ("metal_tile", "mansard_roof_covering"): ("profile_name", "effective_width_mm", "coating", "min_roof_slope_deg"),
    ("board", "roof_batten"): ("width_mm", "thickness_mm", "length_mm"),
    ("rebar", "foundation_reinforcement"): ("diameter_mm", "kg_per_meter", "steel_class"),
    ("rebar", "slab_reinforcement"): ("diameter_mm", "kg_per_meter", "steel_class"),
}


@dataclass(frozen=True)
class MaterialRole:
    role_code: str
    role_name: str
    material_group: str
    usage_context: str
    priority: str
    required_fields: tuple[str, ...]
    recommended_fields: tuple[str, ...]
    module2_hints: Mapping[str, Any]
    warnings: tuple[str, ...]
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class MaterialUsageContext:
    context_code: str
    context_name: str
    material_group: str
    role_codes: tuple[str, ...]
    required_fields: tuple[str, ...]
    module2_hints: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class MaterialRoleEvaluation:
    material_id: str | None
    group_code: str | None
    role: MaterialRole
    applicable: bool
    priority: str
    missing_fields: tuple[str, ...]
    missing_recommended_fields: tuple[str, ...]
    readiness_status: str
    module2_hints: Mapping[str, Any]
    warnings: tuple[str, ...]
    conditions: tuple[str, ...]


@dataclass(frozen=True)
class MaterialRoleReadinessReport:
    material_id: str | None
    material_name: str | None
    group_code: str | None
    roles_found: bool
    status: str
    evaluations: tuple[MaterialRoleEvaluation, ...]
    applicable_role_codes: tuple[str, ...]
    blocked_role_codes: tuple[str, ...]
    primary_roles: tuple[str, ...]
    conditional_roles: tuple[str, ...]
    missing_fields_by_role: Mapping[str, tuple[str, ...]]
    module2_hints: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    message: str


def list_material_roles() -> tuple[MaterialRole, ...]:
    registry = get_material_knowledge_seed_registry()
    roles: list[MaterialRole] = []
    for group_code in sorted(registry.role_mappings):
        roles.extend(get_roles_for_group(group_code, seed_registry=registry))
    return tuple(roles)


def get_roles_for_group(
    group_code: str | None,
    *,
    seed_registry: MaterialKnowledgeSeedRegistry | None = None,
) -> tuple[MaterialRole, ...]:
    resolved_group = _resolve_group_code(group_code)
    if not resolved_group:
        return tuple()
    registry = seed_registry or get_material_knowledge_seed_registry()
    role_mapping = registry.role_mapping(resolved_group)
    if role_mapping is None:
        return tuple()
    return tuple(_build_role(resolved_group, role_code) for role_code in role_mapping.roles)


def get_usage_contexts_for_group(group_code: str | None) -> tuple[MaterialUsageContext, ...]:
    roles = get_roles_for_group(group_code)
    by_context: dict[str, list[MaterialRole]] = {}
    for role in roles:
        by_context.setdefault(role.usage_context, []).append(role)
    contexts: list[MaterialUsageContext] = []
    for context_code, context_roles in sorted(by_context.items()):
        required_fields = tuple(
            dict.fromkeys(field for role in context_roles for field in role.required_fields)
        )
        contexts.append(
            MaterialUsageContext(
                context_code=context_code,
                context_name=_humanize_code(context_code),
                material_group=context_roles[0].material_group,
                role_codes=tuple(role.role_code for role in context_roles),
                required_fields=required_fields,
                module2_hints=tuple(role.module2_hints for role in context_roles),
            )
        )
    return tuple(contexts)


def evaluate_material_roles(technical_profile: MaterialTechnicalProfile | Mapping[str, Any]) -> tuple[MaterialRoleEvaluation, ...]:
    snapshot = _profile_snapshot(technical_profile)
    roles = get_roles_for_group(snapshot["group_code"])
    return tuple(_evaluate_role(snapshot, role) for role in roles)


def build_material_role_readiness_report(
    technical_profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> MaterialRoleReadinessReport:
    snapshot = _profile_snapshot(technical_profile)
    evaluations = evaluate_material_roles(technical_profile)
    applicable = tuple(item.role.role_code for item in evaluations if item.applicable)
    blocked = tuple(item.role.role_code for item in evaluations if not item.applicable)
    missing_by_role = MappingProxyType(
        {item.role.role_code: item.missing_fields for item in evaluations if item.missing_fields}
    )
    warnings = tuple(dict.fromkeys(warning for item in evaluations for warning in item.warnings))
    if not evaluations:
        status = "no_roles"
    elif applicable:
        status = "roles_ready"
    else:
        status = "missing_role_fields"
    return MaterialRoleReadinessReport(
        material_id=snapshot["material_id"],
        material_name=snapshot["material_name"],
        group_code=snapshot["group_code"],
        roles_found=bool(evaluations),
        status=status,
        evaluations=evaluations,
        applicable_role_codes=applicable,
        blocked_role_codes=blocked,
        primary_roles=tuple(item.role.role_code for item in evaluations if item.role.priority == "primary"),
        conditional_roles=tuple(item.role.role_code for item in evaluations if item.role.priority == "conditional"),
        missing_fields_by_role=missing_by_role,
        module2_hints=get_module2_role_hints(technical_profile),
        warnings=warnings,
        message="Material roles evaluated without technology or estimate calculations.",
    )


def get_primary_roles(group_code: str | None) -> tuple[MaterialRole, ...]:
    return tuple(role for role in get_roles_for_group(group_code) if role.priority == "primary")


def get_conditional_roles(group_code: str | None) -> tuple[MaterialRole, ...]:
    return tuple(role for role in get_roles_for_group(group_code) if role.priority == "conditional")


def get_module2_role_hints(technical_profile: MaterialTechnicalProfile | Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    evaluations = evaluate_material_roles(technical_profile)
    return tuple(
        MappingProxyType(
            {
                **dict(item.module2_hints),
                "missingFields": item.missing_fields,
                "readinessStatus": item.readiness_status,
                "module1Only": True,
                "technologyCalculated": False,
                "estimateCalculated": False,
            }
        )
        for item in evaluations
    )


def _build_role(group_code: str, role_code: str) -> MaterialRole:
    meta = ROLE_METADATA.get(role_code, {})
    priority = str(meta.get("priority") or _default_priority(role_code))
    if priority not in VALID_ROLE_PRIORITIES:
        priority = "secondary"
    required_fields = _role_required_fields(group_code, role_code)
    recommended_fields = tuple(
        dict.fromkeys(
            tuple(meta.get("recommended_fields") or ())
            + tuple(CharacteristicSchemaRegistry().get_recommended_characteristics(group_code))
        )
    )
    usage_context = str(meta.get("usage_context") or _usage_context_from_role(role_code))
    hints = _module2_hints(group_code, role_code, usage_context, required_fields)
    return MaterialRole(
        role_code=role_code,
        role_name=str(meta.get("role_name") or _humanize_code(role_code)),
        material_group=group_code,
        usage_context=usage_context,
        priority=priority,
        required_fields=required_fields,
        recommended_fields=recommended_fields,
        module2_hints=MappingProxyType(hints),
        warnings=tuple(meta.get("warnings") or ()),
        conditions=tuple(meta.get("conditions") or ()),
    )


def _evaluate_role(snapshot: Mapping[str, Any], role: MaterialRole) -> MaterialRoleEvaluation:
    characteristics = snapshot["technical_characteristics"]
    missing = tuple(field for field in role.required_fields if _is_missing(characteristics.get(field)))
    missing_recommended = tuple(field for field in role.recommended_fields if _is_missing(characteristics.get(field)))
    warnings = list(role.warnings)
    warnings.extend(_condition_warnings(role, characteristics))
    applicable = not missing and not warnings
    if applicable and role.priority == "conditional":
        readiness_status = "conditional_ready"
    elif applicable:
        readiness_status = "ready"
    else:
        readiness_status = "missing_role_fields" if missing else "condition_not_met"
    hints = {
        **dict(role.module2_hints),
        "missingFields": missing,
        "missingRecommendedFields": missing_recommended,
        "roleReady": applicable,
    }
    return MaterialRoleEvaluation(
        material_id=snapshot["material_id"],
        group_code=snapshot["group_code"],
        role=role,
        applicable=applicable,
        priority=role.priority,
        missing_fields=missing,
        missing_recommended_fields=missing_recommended,
        readiness_status=readiness_status,
        module2_hints=MappingProxyType(hints),
        warnings=tuple(dict.fromkeys(warnings)),
        conditions=role.conditions,
    )


def _role_required_fields(group_code: str, role_code: str) -> tuple[str, ...]:
    override = GROUP_ROLE_FIELD_OVERRIDES.get((group_code, role_code))
    if override is not None:
        return override
    default = GROUP_DEFAULT_ROLE_FIELDS.get(group_code)
    if default is not None:
        return default
    schema = CharacteristicSchemaRegistry().get_schema(group_code)
    if schema is None:
        return tuple()
    return tuple(field.code for field in schema.required)


def _module2_hints(
    group_code: str,
    role_code: str,
    usage_context: str,
    required_fields: tuple[str, ...],
) -> Mapping[str, Any]:
    blueprint = ExtractionBlueprintRegistry().get_blueprint(group_code)
    module2_fields = CharacteristicSchemaRegistry().get_module2_required_characteristics(group_code)
    return {
        "roleCode": role_code,
        "materialGroup": group_code,
        "usageContext": usage_context,
        "possibleTechnologyUsage": usage_context,
        "requiredTechnicalFields": required_fields,
        "module2RequiredFields": module2_fields,
        "unitHints": blueprint.unit_hints if blueprint else tuple(),
        "documentHints": blueprint.document_hints if blueprint else tuple(),
        "module2Calculations": "not_performed_by_module1",
        "module5Costing": "not_performed_by_module1",
    }


def _profile_snapshot(technical_profile: MaterialTechnicalProfile | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(technical_profile, MaterialTechnicalProfile):
        return {
            "material_id": technical_profile.material_id,
            "material_name": technical_profile.material_name,
            "group_code": _resolve_group_code(technical_profile.group_code),
            "technical_characteristics": dict(technical_profile.technical_characteristics),
        }
    return {
        "material_id": _as_string(technical_profile.get("material_id")),
        "material_name": _as_string(technical_profile.get("material_name")),
        "group_code": _resolve_group_code(_as_string(technical_profile.get("group_code"))),
        "technical_characteristics": dict(technical_profile.get("technical_characteristics") or {}),
    }


def _resolve_group_code(group_code: str | None) -> str | None:
    if not group_code:
        return None
    return CharacteristicSchemaRegistry().resolve_group_code(group_code)


def _condition_warnings(role: MaterialRole, characteristics: Mapping[str, Any]) -> tuple[str, ...]:
    warnings: list[str] = []
    for condition in role.conditions:
        if "moisture resistant" in condition:
            board_type = str(characteristics.get("board_type") or "").lower()
            if board_type and not any(token in board_type for token in ("moisture", "wet", "h2", "gkbi")):
                warnings.append("board_type does not confirm moisture resistance.")
    return tuple(warnings)


def _default_priority(role_code: str) -> str:
    if role_code.startswith("requires_") or role_code.endswith("_candidate"):
        return "conditional"
    return "secondary"


def _usage_context_from_role(role_code: str) -> str:
    for token, context in (
        ("foundation", "foundation"),
        ("roof", "roof"),
        ("wall", "walls"),
        ("partition", "partitions"),
        ("facade", "facade"),
        ("floor", "floor"),
        ("lintel", "lintel"),
        ("fence", "fence"),
        ("primer", "substrate_preparation"),
    ):
        if token in role_code:
            return context
    return "general"


def _humanize_code(code: str) -> str:
    return code.replace("_", " ").strip().title()


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (tuple, list, set, dict)):
        return not value
    return False


def _as_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
