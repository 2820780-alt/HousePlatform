from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_alternatives_analogs import get_forbidden_replacements
from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_material_roles import get_roles_for_group
from app.services.module1_material_seed_registry import (
    CompatibilityRuleSeed,
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)
from app.services.module1_technical_profile_packaging import MaterialTechnicalProfile
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


RESULT_TYPES = frozenset(
    {
        "allowed",
        "allowed_with_preparation",
        "conditional",
        "warning",
        "forbidden",
        "insufficient_data",
    }
)

CONTEXT_FIELD_HINTS: Mapping[str, tuple[str, ...]] = {
    "facade_insulation": ("density_kg_m3", "thickness_mm", "application"),
    "formwork_board": ("length_mm", "width_mm", "thickness_mm"),
    "foundation": ("concrete_class", "unit", "application"),
    "foundation_insulation": ("thickness_mm", "compressive_strength_kpa", "water_absorption"),
    "metal_tile_roof": ("profile_name", "effective_width_mm", "coating", "metal_thickness_mm"),
    "plaster": ("consumption_kg_m2_mm", "min_layer_mm", "max_layer_mm"),
    "roof_batten": ("width_mm", "thickness_mm", "length_mm"),
    "warm_floor_tile": ("heated_floor_allowed",),
    "wet_zone": ("board_type",),
}

FORBIDDEN_CONTEXT_HINTS: Mapping[str, tuple[str, ...]] = {
    "gypsum_board_moisture_resistant": ("wet_zone",),
    "tile_adhesive": ("exterior_tile",),
    "acoustic_wool": ("facade_insulation",),
}


@dataclass(frozen=True)
class MaterialPreparationRequirement:
    resource_code: str
    resource_name: str
    required: bool
    status: str
    reason: str


@dataclass(frozen=True)
class MaterialCompatibilityRule:
    context: str
    material_group: str
    substrate_type: str | None
    status: str
    result_type: str
    required_preparation: tuple[MaterialPreparationRequirement, ...]
    explanation: str | None
    warnings: tuple[str, ...]
    module2_hints: Mapping[str, Any]
    module5_hints: Mapping[str, Any]


@dataclass(frozen=True)
class MaterialCompatibilityContext:
    material_group: str | None = None
    substrate_type: str | None = None
    usage_context: str | None = None
    environment: str | None = None
    temperature_condition: str | None = None
    load_condition: str | None = None
    warm_floor: bool | None = None
    interior_exterior: str | None = None
    moisture_exposure: str | None = None
    required_application: str | None = None
    provided_preparation_resources: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class MaterialCompatibilityEvaluation:
    material_id: str | None
    material_name: str | None
    material_group: str | None
    context: MaterialCompatibilityContext
    result_type: str
    allowed: bool
    confidence: Decimal
    required_preparation: tuple[MaterialPreparationRequirement, ...]
    required_material_roles: tuple[str, ...]
    missing_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    forbidden_reasons: tuple[str, ...]
    module2_hints: Mapping[str, Any]
    module5_hints: Mapping[str, Any]
    explanation: str


@dataclass(frozen=True)
class CompatibilityReadinessReport:
    material_id: str | None
    material_name: str | None
    material_group: str | None
    rules_found: bool
    status: str
    rules: tuple[MaterialCompatibilityRule, ...]
    allowed_contexts: tuple[str, ...]
    forbidden_contexts: tuple[str, ...]
    required_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    preparation_actions: tuple[MaterialPreparationRequirement, ...]
    module2_hints: tuple[Mapping[str, Any], ...]
    module5_hints: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    message: str


def list_compatibility_rules() -> tuple[MaterialCompatibilityRule, ...]:
    registry = get_material_knowledge_seed_registry()
    return tuple(_rule_from_seed(rule, seed_registry=registry) for rule in registry.compatibility_rules)


def get_compatibility_rules_for_group(group_code: str | None) -> tuple[MaterialCompatibilityRule, ...]:
    resolved_group = _resolve_group_code(group_code)
    if not resolved_group:
        return tuple()
    return tuple(rule for rule in list_compatibility_rules() if rule.material_group == resolved_group)


def evaluate_material_compatibility(
    material_profile: MaterialTechnicalProfile | Mapping[str, Any],
    context: MaterialCompatibilityContext | Mapping[str, Any],
) -> MaterialCompatibilityEvaluation:
    profile = _profile_snapshot(material_profile)
    compatibility_context = _context_snapshot(context, profile["group_code"])
    rule = _select_rule(profile["group_code"], compatibility_context)
    required_roles = _required_material_roles(profile["group_code"], compatibility_context)
    if rule is None:
        return _insufficient_data_evaluation(profile, compatibility_context, required_roles)
    rule = _rule_with_preparation_status(rule, compatibility_context)

    missing_preparation = tuple(item for item in rule.required_preparation if item.status == "missing")
    missing_fields = _missing_fields(_required_fields_for_context(profile["group_code"], compatibility_context), profile["technical_characteristics"])
    conflicting_fields = _conflicting_fields(profile, compatibility_context)
    result_type = _result_type(rule, missing_preparation, missing_fields, conflicting_fields)
    allowed = result_type in {"allowed", "allowed_with_preparation", "conditional", "warning"}
    forbidden_reasons = _forbidden_reasons(rule, result_type)
    warnings = _evaluation_warnings(rule, result_type, missing_preparation, missing_fields, conflicting_fields)
    return MaterialCompatibilityEvaluation(
        material_id=profile["material_id"],
        material_name=profile["material_name"],
        material_group=profile["group_code"],
        context=compatibility_context,
        result_type=result_type,
        allowed=allowed,
        confidence=_confidence(result_type, missing_preparation, missing_fields, conflicting_fields),
        required_preparation=rule.required_preparation,
        required_material_roles=required_roles,
        missing_fields=missing_fields,
        conflicting_fields=conflicting_fields,
        warnings=warnings,
        forbidden_reasons=forbidden_reasons,
        module2_hints=_module2_hints(rule, compatibility_context, required_roles, missing_fields, conflicting_fields),
        module5_hints=_module5_hints(rule, compatibility_context, required_roles, missing_fields, conflicting_fields),
        explanation=_explanation(rule, result_type, missing_preparation, missing_fields, conflicting_fields),
    )


def build_compatibility_readiness_report(
    material_profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> CompatibilityReadinessReport:
    profile = _profile_snapshot(material_profile)
    rules = get_compatibility_rules_for_group(profile["group_code"])
    required_fields = tuple(dict.fromkeys(field for rule in rules for field in CONTEXT_FIELD_HINTS.get(rule.context, tuple())))
    missing_fields = _missing_fields(required_fields, profile["technical_characteristics"])
    preparation_actions = tuple(item for rule in rules for item in rule.required_preparation)
    warnings: list[str] = []
    if not rules:
        status = "no_compatibility_rules"
    elif missing_fields:
        status = "missing_compatibility_fields"
        warnings.append("Material profile misses fields required for compatibility evaluation.")
    else:
        status = "ready_for_compatibility_evaluation"
    return CompatibilityReadinessReport(
        material_id=profile["material_id"],
        material_name=profile["material_name"],
        material_group=profile["group_code"],
        rules_found=bool(rules),
        status=status,
        rules=rules,
        allowed_contexts=tuple(rule.context for rule in rules if rule.result_type != "forbidden"),
        forbidden_contexts=get_forbidden_contexts(profile["group_code"]),
        required_fields=required_fields,
        missing_fields=missing_fields,
        preparation_actions=preparation_actions,
        module2_hints=tuple(rule.module2_hints for rule in rules),
        module5_hints=tuple(rule.module5_hints for rule in rules),
        warnings=tuple(warnings),
        message="Compatibility readiness evaluated without technology, quantity or cost calculations.",
    )


def get_required_preparation_actions(
    material_profile: MaterialTechnicalProfile | Mapping[str, Any],
    context: MaterialCompatibilityContext | Mapping[str, Any],
) -> tuple[MaterialPreparationRequirement, ...]:
    return tuple(
        item
        for item in evaluate_material_compatibility(material_profile, context).required_preparation
        if item.status == "missing"
    )


def get_forbidden_contexts(group_code: str | None) -> tuple[str, ...]:
    resolved_group = _resolve_group_code(group_code)
    seed_forbidden = tuple(
        rule.context
        for rule in get_compatibility_rules_for_group(resolved_group)
        if rule.result_type == "forbidden"
    )
    alternative_forbidden = tuple(
        rule.target_group
        for rule in get_forbidden_replacements(resolved_group)
    )
    return tuple(dict.fromkeys(seed_forbidden + FORBIDDEN_CONTEXT_HINTS.get(resolved_group or "", tuple()) + alternative_forbidden))


def get_module2_compatibility_hints(
    material_profile: MaterialTechnicalProfile | Mapping[str, Any],
    context: MaterialCompatibilityContext | Mapping[str, Any],
) -> Mapping[str, Any]:
    evaluation = evaluate_material_compatibility(material_profile, context)
    return evaluation.module2_hints


def get_module5_selection_hints(
    material_profile: MaterialTechnicalProfile | Mapping[str, Any],
    context: MaterialCompatibilityContext | Mapping[str, Any],
) -> Mapping[str, Any]:
    evaluation = evaluate_material_compatibility(material_profile, context)
    return evaluation.module5_hints


def _rule_from_seed(
    seed_rule: CompatibilityRuleSeed,
    *,
    seed_registry: MaterialKnowledgeSeedRegistry | None = None,
) -> MaterialCompatibilityRule:
    registry = seed_registry or get_material_knowledge_seed_registry()
    material_group = _resolve_group_code(seed_rule.material) or seed_rule.material
    substrate = _resolve_group_code(seed_rule.substrate) if seed_rule.substrate else None
    requirements = tuple(
        MaterialPreparationRequirement(
            resource_code=resource,
            resource_name=_humanize_code(resource),
            required=True,
            status="missing",
            reason=f"Required by compatibility rule {seed_rule.context}.",
        )
        for resource in seed_rule.required_additional_resources
    )
    result_type = "forbidden" if seed_rule.status == "forbidden" else "warning" if seed_rule.status == "warning" else "allowed"
    warnings = _rule_warnings(seed_rule, registry)
    module2_hints = MappingProxyType(
        {
            "context": seed_rule.context,
            "materialGroup": material_group,
            "substrateType": substrate,
            "requiredPreparationResources": seed_rule.required_additional_resources,
            "technologyCalculated": False,
            "module2Calculations": "not_performed_by_module1",
        }
    )
    module5_hints = MappingProxyType(
        {
            "context": seed_rule.context,
            "materialGroup": material_group,
            "substrateType": substrate,
            "requiredPreparationResources": seed_rule.required_additional_resources,
            "automaticSelection": False,
            "priceCalculated": False,
            "module5Costing": "not_performed_by_module1",
        }
    )
    return MaterialCompatibilityRule(
        context=seed_rule.context,
        material_group=material_group,
        substrate_type=substrate,
        status=seed_rule.status,
        result_type=result_type,
        required_preparation=requirements,
        explanation=seed_rule.explanation,
        warnings=warnings,
        module2_hints=module2_hints,
        module5_hints=module5_hints,
    )


def _select_rule(
    group_code: str | None,
    context: MaterialCompatibilityContext,
) -> MaterialCompatibilityRule | None:
    if not group_code:
        return None
    rules = get_compatibility_rules_for_group(group_code)
    matched = tuple(rule for rule in rules if _rule_matches_context(rule, context))
    if matched:
        return _highest_priority_rule(matched)
    return None


def _rule_with_preparation_status(
    rule: MaterialCompatibilityRule,
    context: MaterialCompatibilityContext,
) -> MaterialCompatibilityRule:
    provided = {_resolve_group_code(item) or item for item in context.provided_preparation_resources}
    requirements = tuple(
        MaterialPreparationRequirement(
            resource_code=item.resource_code,
            resource_name=item.resource_name,
            required=item.required,
            status="provided" if item.resource_code in provided else "missing",
            reason=item.reason,
        )
        for item in rule.required_preparation
    )
    return MaterialCompatibilityRule(
        context=rule.context,
        material_group=rule.material_group,
        substrate_type=rule.substrate_type,
        status=rule.status,
        result_type=rule.result_type,
        required_preparation=requirements,
        explanation=rule.explanation,
        warnings=rule.warnings,
        module2_hints=rule.module2_hints,
        module5_hints=rule.module5_hints,
    )

def _rule_matches_context(rule: MaterialCompatibilityRule, context: MaterialCompatibilityContext) -> bool:
    tokens = _context_tokens(context)
    if rule.context not in tokens:
        return False
    if rule.substrate_type and rule.substrate_type != _resolve_group_code(context.substrate_type):
        return False
    return True


def _context_tokens(context: MaterialCompatibilityContext) -> frozenset[str]:
    tokens = {
        item
        for item in (
            context.usage_context,
            context.environment,
            context.required_application,
            context.moisture_exposure,
            context.interior_exterior,
        )
        if item
    }
    if context.warm_floor:
        tokens.add("warm_floor_tile")
    if context.environment == "wet_room" or context.moisture_exposure in {"wet", "wet_zone"}:
        tokens.add("wet_zone")
        tokens.add("bathroom_tile")
    if context.environment == "roof":
        tokens.add("metal_tile_roof")
        tokens.add("flexible_shingle_roof")
    return frozenset(tokens)


def _highest_priority_rule(rules: tuple[MaterialCompatibilityRule, ...]) -> MaterialCompatibilityRule:
    order = {"forbidden": 0, "warning": 1, "allowed": 2}
    return sorted(rules, key=lambda rule: order.get(rule.result_type, 99))[0]


def _required_fields_for_context(
    group_code: str | None,
    context: MaterialCompatibilityContext,
) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    schema = CharacteristicSchemaRegistry()
    fields = list(schema.get_required_characteristics(group_code))
    for token in _context_tokens(context):
        fields.extend(CONTEXT_FIELD_HINTS.get(token, tuple()))
    matching_roles = tuple(
        role
        for role in get_roles_for_group(group_code)
        if role.role_code in _context_tokens(context) or role.usage_context in _context_tokens(context)
    )
    for role in matching_roles:
        fields.extend(role.required_fields)
    return tuple(dict.fromkeys(fields))


def _required_material_roles(
    group_code: str | None,
    context: MaterialCompatibilityContext,
) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    tokens = _context_tokens(context)
    roles = tuple(
        role.role_code
        for role in get_roles_for_group(group_code)
        if role.role_code in tokens or role.usage_context in tokens or role.priority == "primary"
    )
    return tuple(dict.fromkeys(roles))


def _result_type(
    rule: MaterialCompatibilityRule,
    missing_preparation: tuple[MaterialPreparationRequirement, ...],
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
) -> str:
    if rule.result_type == "forbidden":
        return "forbidden"
    if missing_fields:
        return "insufficient_data"
    if rule.result_type == "warning" and (missing_preparation or conflicting_fields):
        return "conditional"
    if rule.result_type == "warning":
        return "warning"
    if missing_preparation:
        return "allowed_with_preparation"
    return "allowed"


def _confidence(
    result_type: str,
    missing_preparation: tuple[MaterialPreparationRequirement, ...],
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
) -> Decimal:
    base = {
        "allowed": Decimal("0.90"),
        "allowed_with_preparation": Decimal("0.78"),
        "conditional": Decimal("0.55"),
        "warning": Decimal("0.62"),
        "forbidden": Decimal("0.0"),
        "insufficient_data": Decimal("0.20"),
    }[result_type]
    penalty = Decimal("0.04") * Decimal(len(missing_preparation) + len(missing_fields) + len(conflicting_fields))
    return max(Decimal("0"), base - penalty)


def _module2_hints(
    rule: MaterialCompatibilityRule,
    context: MaterialCompatibilityContext,
    required_roles: tuple[str, ...],
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            **dict(rule.module2_hints),
            "usageContext": context.usage_context,
            "environment": context.environment,
            "requiredMaterialRoles": required_roles,
            "missingFields": missing_fields,
            "conflictingFields": conflicting_fields,
            "automaticMaterialSelection": False,
            "technologyCalculated": False,
        }
    )


def _module5_hints(
    rule: MaterialCompatibilityRule,
    context: MaterialCompatibilityContext,
    required_roles: tuple[str, ...],
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            **dict(rule.module5_hints),
            "usageContext": context.usage_context,
            "environment": context.environment,
            "requiredMaterialRoles": required_roles,
            "missingFields": missing_fields,
            "conflictingFields": conflicting_fields,
            "automaticSelection": False,
            "priceCalculated": False,
            "estimateCalculated": False,
        }
    )


def _insufficient_data_evaluation(
    profile: Mapping[str, Any],
    context: MaterialCompatibilityContext,
    required_roles: tuple[str, ...],
) -> MaterialCompatibilityEvaluation:
    fallback_rule = MaterialCompatibilityRule(
        context=context.usage_context or context.environment or "unknown",
        material_group=profile["group_code"] or "",
        substrate_type=context.substrate_type,
        status="insufficient_data",
        result_type="insufficient_data",
        required_preparation=tuple(),
        explanation=None,
        warnings=("No seed compatibility rule found for this context.",),
        module2_hints=MappingProxyType(
            {
                "context": context.usage_context,
                "materialGroup": profile["group_code"],
                "technologyCalculated": False,
                "module2Calculations": "not_performed_by_module1",
            }
        ),
        module5_hints=MappingProxyType(
            {
                "context": context.usage_context,
                "materialGroup": profile["group_code"],
                "automaticSelection": False,
                "priceCalculated": False,
                "module5Costing": "not_performed_by_module1",
            }
        ),
    )
    return MaterialCompatibilityEvaluation(
        material_id=profile["material_id"],
        material_name=profile["material_name"],
        material_group=profile["group_code"],
        context=context,
        result_type="insufficient_data",
        allowed=False,
        confidence=Decimal("0.10"),
        required_preparation=tuple(),
        required_material_roles=required_roles,
        missing_fields=tuple(),
        conflicting_fields=tuple(),
        warnings=fallback_rule.warnings,
        forbidden_reasons=tuple(),
        module2_hints=_module2_hints(fallback_rule, context, required_roles, tuple(), tuple()),
        module5_hints=_module5_hints(fallback_rule, context, required_roles, tuple(), tuple()),
        explanation="No seed compatibility rule found; Module 1 did not select or calculate material usage.",
    )


def _forbidden_reasons(rule: MaterialCompatibilityRule, result_type: str) -> tuple[str, ...]:
    if result_type != "forbidden":
        return tuple()
    return (rule.explanation or "Forbidden by compatibility rule.",)


def _evaluation_warnings(
    rule: MaterialCompatibilityRule,
    result_type: str,
    missing_preparation: tuple[MaterialPreparationRequirement, ...],
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
) -> tuple[str, ...]:
    warnings = list(rule.warnings)
    if missing_preparation:
        warnings.append("Required preparation resources are missing.")
    if missing_fields:
        warnings.append("Material profile misses fields required for compatibility evaluation.")
    if conflicting_fields:
        warnings.append("Material/context fields conflict and require manual review.")
    if result_type == "forbidden":
        warnings.append("Context is forbidden by compatibility rule.")
    return tuple(dict.fromkeys(warnings))


def _explanation(
    rule: MaterialCompatibilityRule,
    result_type: str,
    missing_preparation: tuple[MaterialPreparationRequirement, ...],
    missing_fields: tuple[str, ...],
    conflicting_fields: tuple[str, ...],
) -> str:
    if result_type == "forbidden":
        return rule.explanation or "Compatibility is forbidden by seed rule."
    if missing_fields:
        return "Compatibility cannot be confirmed until required fields are present."
    if conflicting_fields:
        return "Compatibility requires manual review because fields conflict."
    if missing_preparation:
        return "Material is compatible only with required preparation actions."
    return rule.explanation or "Compatibility rule matched without calculations."


def _rule_warnings(
    seed_rule: CompatibilityRuleSeed,
    seed_registry: MaterialKnowledgeSeedRegistry,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if seed_rule.status == "forbidden":
        warnings.append("Forbidden compatibility context from seed.")
    if seed_rule.material and not seed_registry.has_material_group(seed_rule.material):
        warnings.append(f"Material group is not present in taxonomy: {seed_rule.material}")
    if seed_rule.substrate and not seed_registry.has_material_group(seed_rule.substrate):
        warnings.append(f"Substrate group is not present in taxonomy: {seed_rule.substrate}")
    return tuple(warnings)


def _profile_snapshot(profile: MaterialTechnicalProfile | Mapping[str, Any]) -> Mapping[str, Any]:
    if isinstance(profile, MaterialTechnicalProfile):
        return {
            "material_id": profile.material_id,
            "material_name": profile.material_name,
            "group_code": _resolve_group_code(profile.group_code),
            "technical_characteristics": dict(profile.technical_characteristics),
            "base_unit": UnitConversionRegistry().normalize_unit(profile.base_unit) or profile.base_unit,
        }
    return {
        "material_id": _as_string(profile.get("material_id")),
        "material_name": _as_string(profile.get("material_name")),
        "group_code": _resolve_group_code(_as_string(profile.get("group_code"))),
        "technical_characteristics": dict(profile.get("technical_characteristics") or {}),
        "base_unit": UnitConversionRegistry().normalize_unit(_as_string(profile.get("base_unit"))) or _as_string(profile.get("base_unit")),
    }


def _context_snapshot(
    context: MaterialCompatibilityContext | Mapping[str, Any],
    fallback_group: str | None,
) -> MaterialCompatibilityContext:
    if isinstance(context, MaterialCompatibilityContext):
        return MaterialCompatibilityContext(
            material_group=_resolve_group_code(context.material_group) or fallback_group,
            substrate_type=_resolve_group_code(context.substrate_type) or context.substrate_type,
            usage_context=context.usage_context,
            environment=context.environment,
            temperature_condition=context.temperature_condition,
            load_condition=context.load_condition,
            warm_floor=context.warm_floor,
            interior_exterior=context.interior_exterior,
            moisture_exposure=context.moisture_exposure,
            required_application=context.required_application,
            provided_preparation_resources=context.provided_preparation_resources,
        )
    return MaterialCompatibilityContext(
        material_group=_resolve_group_code(_as_string(context.get("material_group"))) or fallback_group,
        substrate_type=_resolve_group_code(_as_string(context.get("substrate_type"))) or _as_string(context.get("substrate_type")),
        usage_context=_as_string(context.get("usage_context")),
        environment=_as_string(context.get("environment")),
        temperature_condition=_as_string(context.get("temperature_condition")),
        load_condition=_as_string(context.get("load_condition")),
        warm_floor=context.get("warm_floor") if isinstance(context.get("warm_floor"), bool) else None,
        interior_exterior=_as_string(context.get("interior_exterior")),
        moisture_exposure=_as_string(context.get("moisture_exposure")),
        required_application=_as_string(context.get("required_application")),
        provided_preparation_resources=tuple(str(item) for item in context.get("provided_preparation_resources", ()) or ()),
    )


def _missing_fields(fields: tuple[str, ...], characteristics: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in fields if _is_missing(characteristics.get(field)))


def _conflicting_fields(
    profile: Mapping[str, Any],
    context: MaterialCompatibilityContext,
) -> tuple[str, ...]:
    conflicts: list[str] = []
    characteristics = profile["technical_characteristics"]
    if context.warm_floor and characteristics.get("heated_floor_allowed") is False:
        conflicts.append("heated_floor_allowed")
    if context.environment == "exterior" and characteristics.get("exterior_allowed") is False:
        conflicts.append("exterior_allowed")
    if context.moisture_exposure in {"wet", "wet_zone"}:
        board_type = str(characteristics.get("board_type") or "").lower()
        if board_type == "regular":
            conflicts.append("board_type")
    return tuple(conflicts)


def _resolve_group_code(group_code: str | None) -> str | None:
    if not group_code:
        return None
    return CharacteristicSchemaRegistry().resolve_group_code(group_code)


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
