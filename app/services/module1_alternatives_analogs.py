from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_characteristic_schema_registry import CharacteristicSchemaRegistry
from app.services.module1_material_roles import get_module2_role_hints
from app.services.module1_material_seed_registry import (
    AlternativeRuleSeed,
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)
from app.services.module1_technical_profile_packaging import MaterialTechnicalProfile
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


ALTERNATIVE_TYPES = frozenset(
    {
        "full_analog",
        "technical_alternative",
        "functional_alternative",
        "conditional_replacement",
        "forbidden_replacement",
    }
)

CONFIDENCE_BY_TYPE: Mapping[str, Decimal] = {
    "full_analog": Decimal("0.95"),
    "technical_alternative": Decimal("0.78"),
    "functional_alternative": Decimal("0.55"),
    "conditional_replacement": Decimal("0.45"),
    "forbidden_replacement": Decimal("0.0"),
}

CONDITION_FIELD_HINTS: Mapping[str, tuple[str, ...]] = {
    "compare_consumption_and_layer_limits": ("consumption_kg_m2_mm", "min_layer_mm", "max_layer_mm"),
    "depends_on_room_and_substrate": ("application", "compatible_substrates"),
    "depends_on_usage_role_and_dimensions": ("application_hint", "length_mm", "width_mm", "thickness_mm"),
    "match_class_mobility_frost_and_water_resistance": (
        "concrete_class",
        "mobility_class",
        "frost_resistance",
        "water_resistance",
    ),
    "match_density_thickness_and_application": ("density_kg_m3", "thickness_mm", "application"),
    "match_diameter_steel_class_and_profile": ("diameter_mm", "steel_class", "profile_type"),
    "match_indoor_outdoor_frost_and_heated_floor_support": (
        "application",
        "frost_resistant",
        "heated_floor_allowed",
    ),
    "match_profile_effective_width_coating_and_thickness": (
        "profile_name",
        "effective_width_mm",
        "coating",
        "metal_thickness_mm",
    ),
    "match_thickness_type_and_application": ("thickness_mm", "board_type", "application"),
    "not_foundation_or_high_moisture_or_high_load": (
        "application",
        "compressive_strength_kpa",
        "water_absorption",
    ),
    "user_changes_floor_technology": ("floor_technology", "dry_system_allowed"),
    "wet_room_or_higher_requirement": ("board_type", "application"),
    "wet_zone": ("board_type", "application"),
}


@dataclass(frozen=True)
class MaterialAlternativeRule:
    source_group: str
    target_group: str
    alternative_type: str
    recalculation_required: bool
    technology_change_required: bool
    condition: str | None
    required_matching_fields: tuple[str, ...]
    module2_hints: Mapping[str, Any]
    module5_hints: Mapping[str, Any]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MaterialAlternativeCandidate:
    source_group: str
    target_group: str
    alternative_type: str
    allowed: bool
    confidence: Decimal
    required_matching_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    rule: MaterialAlternativeRule


@dataclass(frozen=True)
class MaterialAlternativeEvaluation:
    source_material_id: str | None
    source_material_name: str | None
    source_group: str | None
    target_material_id: str | None
    target_material_name: str | None
    target_group: str | None
    alternative_type: str
    allowed: bool
    confidence: Decimal
    required_matching_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    conflicting_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    module2_hints: Mapping[str, Any]
    module5_hints: Mapping[str, Any]
    explanation: str


@dataclass(frozen=True)
class MaterialAlternativeReadinessReport:
    source_material_id: str | None
    source_material_name: str | None
    source_group: str | None
    rules_found: bool
    status: str
    rules: tuple[MaterialAlternativeRule, ...]
    candidates: tuple[MaterialAlternativeCandidate, ...]
    allowed_target_groups: tuple[str, ...]
    forbidden_target_groups: tuple[str, ...]
    required_fields: tuple[str, ...]
    missing_fields: tuple[str, ...]
    module2_hints: tuple[Mapping[str, Any], ...]
    module5_hints: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]
    message: str


def list_alternative_rules() -> tuple[MaterialAlternativeRule, ...]:
    registry = get_material_knowledge_seed_registry()
    return tuple(_rule_from_seed(rule, seed_registry=registry) for rule in registry.alternative_rules)


def get_alternative_rules_for_group(group_code: str | None) -> tuple[MaterialAlternativeRule, ...]:
    resolved_group = _resolve_group_code(group_code)
    if not resolved_group:
        return tuple()
    return tuple(rule for rule in list_alternative_rules() if rule.source_group == resolved_group)


def get_allowed_alternative_groups(group_code: str | None) -> tuple[str, ...]:
    return tuple(
        dict.fromkeys(
            rule.target_group
            for rule in get_alternative_rules_for_group(group_code)
            if rule.alternative_type != "forbidden_replacement"
        )
    )


def get_forbidden_replacements(group_code: str | None) -> tuple[MaterialAlternativeRule, ...]:
    return tuple(
        rule
        for rule in get_alternative_rules_for_group(group_code)
        if rule.alternative_type == "forbidden_replacement"
    )


def evaluate_material_alternative(
    source_profile: MaterialTechnicalProfile | Mapping[str, Any],
    target_profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> MaterialAlternativeEvaluation:
    source = _profile_snapshot(source_profile)
    target = _profile_snapshot(target_profile)
    rule = _select_rule(source["group_code"], target["group_code"])
    if rule is None:
        return _unknown_evaluation(source, target)

    source_fields = source["technical_characteristics"]
    target_fields = target["technical_characteristics"]
    missing = _missing_matching_fields(rule.required_matching_fields, source_fields, target_fields)
    conflicts = _conflicting_matching_fields(rule.required_matching_fields, source_fields, target_fields)
    allowed = rule.alternative_type != "forbidden_replacement" and not missing and not conflicts
    confidence = _confidence(rule, allowed, missing, conflicts)
    warnings = list(rule.warnings)
    if missing:
        warnings.append("Alternative requires missing technical fields.")
    if conflicts:
        warnings.append("Alternative has conflicting technical fields.")
    if rule.recalculation_required:
        warnings.append("Module 2/Module 5 must review recalculation hints; Module 1 did not calculate.")
    if rule.technology_change_required:
        warnings.append("Technology change hint only; Module 1 did not change technology.")
    return MaterialAlternativeEvaluation(
        source_material_id=source["material_id"],
        source_material_name=source["material_name"],
        source_group=source["group_code"],
        target_material_id=target["material_id"],
        target_material_name=target["material_name"],
        target_group=target["group_code"],
        alternative_type=rule.alternative_type,
        allowed=allowed,
        confidence=confidence,
        required_matching_fields=rule.required_matching_fields,
        missing_fields=missing,
        conflicting_fields=conflicts,
        warnings=tuple(dict.fromkeys(warnings)),
        module2_hints=_evaluation_module2_hints(rule, missing, conflicts),
        module5_hints=_evaluation_module5_hints(rule, missing, conflicts),
        explanation=_evaluation_explanation(rule, allowed, missing, conflicts),
    )


def build_alternative_readiness_report(
    source_profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> MaterialAlternativeReadinessReport:
    source = _profile_snapshot(source_profile)
    rules = get_alternative_rules_for_group(source["group_code"])
    candidates = tuple(_candidate_from_rule(source, rule) for rule in rules)
    required_fields = tuple(dict.fromkeys(field for rule in rules for field in rule.required_matching_fields))
    missing_fields = tuple(field for field in required_fields if _is_missing(source["technical_characteristics"].get(field)))
    warnings: list[str] = []
    if not rules:
        status = "no_alternative_rules"
    elif missing_fields:
        status = "missing_alternative_fields"
        warnings.append("Source profile misses fields required for safe alternative evaluation.")
    else:
        status = "ready_for_alternative_evaluation"
    return MaterialAlternativeReadinessReport(
        source_material_id=source["material_id"],
        source_material_name=source["material_name"],
        source_group=source["group_code"],
        rules_found=bool(rules),
        status=status,
        rules=rules,
        candidates=candidates,
        allowed_target_groups=get_allowed_alternative_groups(source["group_code"]),
        forbidden_target_groups=tuple(rule.target_group for rule in rules if rule.alternative_type == "forbidden_replacement"),
        required_fields=required_fields,
        missing_fields=missing_fields,
        module2_hints=get_module2_alternative_hints(source_profile),
        module5_hints=get_module5_selection_hints(source_profile),
        warnings=tuple(warnings),
        message="Alternative readiness evaluated without automatic material replacement.",
    )


def get_module2_alternative_hints(
    source_profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    source = _profile_snapshot(source_profile)
    role_hints = get_module2_role_hints(source_profile)
    hints: list[Mapping[str, Any]] = []
    for rule in get_alternative_rules_for_group(source["group_code"]):
        hints.append(
            MappingProxyType(
                {
                    **dict(rule.module2_hints),
                    "roleHints": role_hints,
                    "automaticReplacement": False,
                    "technologyCalculated": False,
                }
            )
        )
    return tuple(hints)


def get_module5_selection_hints(
    source_profile: MaterialTechnicalProfile | Mapping[str, Any],
) -> tuple[Mapping[str, Any], ...]:
    source = _profile_snapshot(source_profile)
    return tuple(
        MappingProxyType(
            {
                **dict(rule.module5_hints),
                "sourceMaterialId": source["material_id"],
                "sourceMaterialName": source["material_name"],
                "sourceGroup": source["group_code"],
                "targetGroup": rule.target_group,
                "automaticSelection": False,
                "priceCalculated": False,
                "estimateCalculated": False,
            }
        )
        for rule in get_alternative_rules_for_group(source["group_code"])
    )


def _rule_from_seed(
    seed_rule: AlternativeRuleSeed,
    *,
    seed_registry: MaterialKnowledgeSeedRegistry | None = None,
) -> MaterialAlternativeRule:
    registry = seed_registry or get_material_knowledge_seed_registry()
    source = _resolve_group_code(seed_rule.from_material) or seed_rule.from_material
    target = _resolve_group_code(seed_rule.to_material) or seed_rule.to_material
    alternative_type = _normalize_alternative_type(seed_rule.alternative_type)
    fields = _required_matching_fields(source, target, seed_rule.condition)
    warnings = _rule_warnings(seed_rule, alternative_type, registry)
    module2_hints = MappingProxyType(
        {
            "sourceGroup": source,
            "targetGroup": target,
            "alternativeType": alternative_type,
            "requiredMatchingFields": fields,
            "condition": seed_rule.condition,
            "recalculationRequired": seed_rule.recalculation_required,
            "technologyChangeRequired": seed_rule.technology_change_required,
            "technologyCalculated": False,
            "module2Calculations": "not_performed_by_module1",
        }
    )
    module5_hints = MappingProxyType(
        {
            "sourceGroup": source,
            "targetGroup": target,
            "alternativeType": alternative_type,
            "requiredMatchingFields": fields,
            "recalculationRequired": seed_rule.recalculation_required,
            "automaticSelection": False,
            "priceCalculated": False,
            "module5Costing": "not_performed_by_module1",
        }
    )
    return MaterialAlternativeRule(
        source_group=source,
        target_group=target,
        alternative_type=alternative_type,
        recalculation_required=seed_rule.recalculation_required,
        technology_change_required=seed_rule.technology_change_required,
        condition=seed_rule.condition,
        required_matching_fields=fields,
        module2_hints=module2_hints,
        module5_hints=module5_hints,
        warnings=warnings,
    )


def _select_rule(source_group: str | None, target_group: str | None) -> MaterialAlternativeRule | None:
    if not source_group or not target_group:
        return None
    rules = get_alternative_rules_for_group(source_group)
    exact = tuple(rule for rule in rules if rule.target_group == target_group)
    if exact:
        return _highest_priority_rule(exact)
    if source_group == target_group:
        return _synthetic_same_group_rule(source_group)
    return None


def _synthetic_same_group_rule(group_code: str) -> MaterialAlternativeRule:
    fields = _required_matching_fields(group_code, group_code, None)
    return MaterialAlternativeRule(
        source_group=group_code,
        target_group=group_code,
        alternative_type="full_analog",
        recalculation_required=False,
        technology_change_required=False,
        condition="same_material_group_full_analog",
        required_matching_fields=fields,
        module2_hints=MappingProxyType(
            {
                "sourceGroup": group_code,
                "targetGroup": group_code,
                "alternativeType": "full_analog",
                "requiredMatchingFields": fields,
                "technologyCalculated": False,
                "module2Calculations": "not_performed_by_module1",
            }
        ),
        module5_hints=MappingProxyType(
            {
                "sourceGroup": group_code,
                "targetGroup": group_code,
                "alternativeType": "full_analog",
                "requiredMatchingFields": fields,
                "automaticSelection": False,
                "priceCalculated": False,
                "module5Costing": "not_performed_by_module1",
            }
        ),
        warnings=tuple(),
    )


def _highest_priority_rule(rules: tuple[MaterialAlternativeRule, ...]) -> MaterialAlternativeRule:
    order = {
        "forbidden_replacement": 0,
        "conditional_replacement": 1,
        "functional_alternative": 2,
        "technical_alternative": 3,
        "full_analog": 4,
    }
    return sorted(rules, key=lambda rule: order.get(rule.alternative_type, 99))[0]


def _candidate_from_rule(
    source: Mapping[str, Any],
    rule: MaterialAlternativeRule,
) -> MaterialAlternativeCandidate:
    missing = tuple(field for field in rule.required_matching_fields if _is_missing(source["technical_characteristics"].get(field)))
    allowed = rule.alternative_type != "forbidden_replacement" and not missing
    return MaterialAlternativeCandidate(
        source_group=rule.source_group,
        target_group=rule.target_group,
        alternative_type=rule.alternative_type,
        allowed=allowed,
        confidence=_confidence(rule, allowed, missing, tuple()),
        required_matching_fields=rule.required_matching_fields,
        warnings=rule.warnings,
        rule=rule,
    )


def _unknown_evaluation(
    source: Mapping[str, Any],
    target: Mapping[str, Any],
) -> MaterialAlternativeEvaluation:
    return MaterialAlternativeEvaluation(
        source_material_id=source["material_id"],
        source_material_name=source["material_name"],
        source_group=source["group_code"],
        target_material_id=target["material_id"],
        target_material_name=target["material_name"],
        target_group=target["group_code"],
        alternative_type="unknown",
        allowed=False,
        confidence=Decimal("0"),
        required_matching_fields=tuple(),
        missing_fields=tuple(),
        conflicting_fields=tuple(),
        warnings=("No seed alternative rule found for this replacement.",),
        module2_hints=MappingProxyType(
            {
                "sourceGroup": source["group_code"],
                "targetGroup": target["group_code"],
                "technologyCalculated": False,
                "module2Calculations": "not_performed_by_module1",
            }
        ),
        module5_hints=MappingProxyType(
            {
                "sourceGroup": source["group_code"],
                "targetGroup": target["group_code"],
                "automaticSelection": False,
                "priceCalculated": False,
                "module5Costing": "not_performed_by_module1",
            }
        ),
        explanation="No seed alternative rule found; Module 1 does not auto-select replacements.",
    )


def _required_matching_fields(source: str, target: str, condition: str | None) -> tuple[str, ...]:
    schema = CharacteristicSchemaRegistry()
    source_fields = set(schema.get_required_characteristics(source))
    target_fields = set(schema.get_required_characteristics(target))
    common = tuple(sorted(source_fields.intersection(target_fields)))
    condition_fields = CONDITION_FIELD_HINTS.get(condition or "", tuple())
    if common:
        return tuple(dict.fromkeys(common + condition_fields))
    if condition_fields:
        return condition_fields
    return tuple(sorted(source_fields or target_fields))


def _missing_matching_fields(
    fields: tuple[str, ...],
    source_fields: Mapping[str, Any],
    target_fields: Mapping[str, Any],
) -> tuple[str, ...]:
    missing: list[str] = []
    for field in fields:
        if _is_missing(source_fields.get(field)):
            missing.append(f"source.{field}")
        if _is_missing(target_fields.get(field)):
            missing.append(f"target.{field}")
    return tuple(missing)


def _conflicting_matching_fields(
    fields: tuple[str, ...],
    source_fields: Mapping[str, Any],
    target_fields: Mapping[str, Any],
) -> tuple[str, ...]:
    conflicts: list[str] = []
    for field in fields:
        source_value = source_fields.get(field)
        target_value = target_fields.get(field)
        if _is_missing(source_value) or _is_missing(target_value):
            continue
        if _normalized_value(source_value) != _normalized_value(target_value):
            conflicts.append(field)
    return tuple(conflicts)


def _confidence(
    rule: MaterialAlternativeRule,
    allowed: bool,
    missing: tuple[str, ...],
    conflicts: tuple[str, ...],
) -> Decimal:
    if not allowed:
        if rule.alternative_type == "forbidden_replacement":
            return Decimal("0")
        penalty = Decimal("0.08") * Decimal(len(missing) + len(conflicts))
        base = CONFIDENCE_BY_TYPE.get(rule.alternative_type, Decimal("0.2"))
        return max(Decimal("0.05"), base - penalty)
    return CONFIDENCE_BY_TYPE.get(rule.alternative_type, Decimal("0.5"))


def _evaluation_module2_hints(
    rule: MaterialAlternativeRule,
    missing: tuple[str, ...],
    conflicts: tuple[str, ...],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            **dict(rule.module2_hints),
            "missingFields": missing,
            "conflictingFields": conflicts,
            "automaticReplacement": False,
            "technologyCalculated": False,
        }
    )


def _evaluation_module5_hints(
    rule: MaterialAlternativeRule,
    missing: tuple[str, ...],
    conflicts: tuple[str, ...],
) -> Mapping[str, Any]:
    return MappingProxyType(
        {
            **dict(rule.module5_hints),
            "missingFields": missing,
            "conflictingFields": conflicts,
            "automaticSelection": False,
            "priceCalculated": False,
            "estimateCalculated": False,
        }
    )


def _evaluation_explanation(
    rule: MaterialAlternativeRule,
    allowed: bool,
    missing: tuple[str, ...],
    conflicts: tuple[str, ...],
) -> str:
    if rule.alternative_type == "forbidden_replacement":
        return "Replacement is forbidden by seed rule."
    if missing:
        return "Replacement cannot be confirmed until required fields are present."
    if conflicts:
        return "Replacement requires manual review because matching fields conflict."
    if allowed:
        return "Alternative rule matched; Module 1 returned hints only and did not replace material."
    return "Alternative requires manual review."


def _rule_warnings(
    seed_rule: AlternativeRuleSeed,
    alternative_type: str,
    seed_registry: MaterialKnowledgeSeedRegistry,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if alternative_type == "forbidden_replacement":
        warnings.append("Replacement is forbidden by material knowledge seed.")
    if seed_rule.recalculation_required:
        warnings.append("Quantity/resource recalculation may be required outside Module 1.")
    if seed_rule.technology_change_required:
        warnings.append("Technology change may be required outside Module 1.")
    if not seed_registry.has_material_group(seed_rule.from_material):
        warnings.append(f"Source group is not present in taxonomy: {seed_rule.from_material}")
    if not seed_registry.has_material_group(seed_rule.to_material):
        warnings.append(f"Target group is not present in taxonomy: {seed_rule.to_material}")
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


def _normalize_alternative_type(alternative_type: str) -> str:
    if alternative_type == "conditional_alternative":
        return "conditional_replacement"
    return alternative_type


def _resolve_group_code(group_code: str | None) -> str | None:
    if not group_code:
        return None
    return CharacteristicSchemaRegistry().resolve_group_code(group_code)


def _normalized_value(value: Any) -> str:
    if isinstance(value, Decimal):
        return str(value.normalize())
    return str(value).strip().lower()


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
