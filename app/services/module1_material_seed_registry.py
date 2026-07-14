from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DEFAULT_MATERIAL_KNOWLEDGE_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "src/modules/module1/seeds/material_knowledge_seed.json"
)

REQUIRED_SEED_SECTIONS = (
    "version",
    "module",
    "purpose",
    "boundaries",
    "taxonomy",
    "characteristicSchemas",
    "roleMappings",
    "compatibilityRules",
    "alternativeRules",
    "unitConversions",
)

KEY_MATERIAL_GROUPS = (
    "aerated_concrete_block",
    "rebar",
    "board",
    "ready_mix_concrete",
    "metal_tile",
    "mineral_wool_slab",
)


class MaterialKnowledgeSeedError(ValueError):
    pass


@dataclass(frozen=True)
class TaxonomyGroup:
    code: str
    name: str
    children: tuple[str, ...]


@dataclass(frozen=True)
class CharacteristicSchemaSeed:
    material_group: str
    required: tuple[str, ...]
    module2_required: tuple[str, ...]
    recommended: tuple[str, ...]


@dataclass(frozen=True)
class RoleMappingSeed:
    material_group: str
    roles: tuple[str, ...]


@dataclass(frozen=True)
class CompatibilityRuleSeed:
    context: str
    material: str
    substrate: str
    status: str
    required_additional_resources: tuple[str, ...]
    explanation: str | None = None


@dataclass(frozen=True)
class AlternativeRuleSeed:
    from_material: str
    to_material: str
    alternative_type: str
    recalculation_required: bool = False
    technology_change_required: bool = False
    condition: str | None = None


@dataclass(frozen=True)
class UnitConversionRuleSeed:
    material_group: str
    from_unit: str
    to_unit: str
    formula: str
    fallback: str | None = None


@dataclass(frozen=True)
class MaterialKnowledgeSeedRegistry:
    version: str
    module: str
    purpose: str
    boundaries: Mapping[str, Any]
    taxonomy: tuple[TaxonomyGroup, ...]
    characteristic_schemas: Mapping[str, CharacteristicSchemaSeed]
    role_mappings: Mapping[str, RoleMappingSeed]
    compatibility_rules: tuple[CompatibilityRuleSeed, ...]
    alternative_rules: tuple[AlternativeRuleSeed, ...]
    unit_conversions: tuple[UnitConversionRuleSeed, ...]

    def taxonomy_codes(self) -> tuple[str, ...]:
        return tuple(group.code for group in self.taxonomy)

    def material_group_codes(self) -> frozenset[str]:
        codes: set[str] = set()
        for group in self.taxonomy:
            codes.add(group.code)
            codes.update(group.children)
        return frozenset(codes)

    def has_material_group(self, group_code: str) -> bool:
        return group_code in self.material_group_codes()

    def get_taxonomy_group(self, code: str) -> TaxonomyGroup | None:
        return next((group for group in self.taxonomy if group.code == code), None)

    def get_characteristic_schema(self, material_group: str) -> CharacteristicSchemaSeed | None:
        return self.characteristic_schemas.get(material_group)

    def required_characteristics(self, material_group: str) -> tuple[str, ...]:
        schema = self.get_characteristic_schema(material_group)
        return schema.required if schema else tuple()

    def module2_required_characteristics(self, material_group: str) -> tuple[str, ...]:
        schema = self.get_characteristic_schema(material_group)
        return schema.module2_required if schema else tuple()

    def role_mapping(self, material_group: str) -> RoleMappingSeed | None:
        return self.role_mappings.get(material_group)

    def compatibility_for_material(self, material: str) -> tuple[CompatibilityRuleSeed, ...]:
        return tuple(rule for rule in self.compatibility_rules if rule.material == material)

    def alternatives_from(self, material: str) -> tuple[AlternativeRuleSeed, ...]:
        return tuple(rule for rule in self.alternative_rules if rule.from_material == material)

    def unit_conversions_for_group(self, material_group: str) -> tuple[UnitConversionRuleSeed, ...]:
        return tuple(rule for rule in self.unit_conversions if rule.material_group == material_group)


def load_material_knowledge_seed(
    path: Path | str = DEFAULT_MATERIAL_KNOWLEDGE_SEED_PATH,
) -> MaterialKnowledgeSeedRegistry:
    seed_path = Path(path)
    if not seed_path.exists():
        raise MaterialKnowledgeSeedError(f"Module 1 material knowledge seed not found: {seed_path}")
    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MaterialKnowledgeSeedError(f"Module 1 material knowledge seed is not valid JSON: {exc}") from exc
    return build_material_knowledge_seed_registry(raw)


@lru_cache(maxsize=1)
def get_material_knowledge_seed_registry() -> MaterialKnowledgeSeedRegistry:
    return load_material_knowledge_seed(DEFAULT_MATERIAL_KNOWLEDGE_SEED_PATH)


def build_material_knowledge_seed_registry(raw: Mapping[str, Any]) -> MaterialKnowledgeSeedRegistry:
    errors = validate_material_knowledge_seed(raw)
    if errors:
        raise MaterialKnowledgeSeedError("; ".join(errors))

    taxonomy = tuple(
        TaxonomyGroup(
            code=str(item["code"]),
            name=str(item["name"]),
            children=tuple(str(child) for child in item["children"]),
        )
        for item in raw["taxonomy"]
    )

    characteristic_schemas = MappingProxyType(
        {
            str(group_code): CharacteristicSchemaSeed(
                material_group=str(group_code),
                required=_str_tuple(schema["required"]),
                module2_required=_str_tuple(schema["module2Required"]),
                recommended=_str_tuple(schema["recommended"]),
            )
            for group_code, schema in raw["characteristicSchemas"].items()
        }
    )

    role_mappings = MappingProxyType(
        {
            str(item["materialGroup"]): RoleMappingSeed(
                material_group=str(item["materialGroup"]),
                roles=_str_tuple(item["roles"]),
            )
            for item in raw["roleMappings"]
        }
    )

    compatibility_rules = tuple(
        CompatibilityRuleSeed(
            context=str(item["context"]),
            material=str(item["material"]),
            substrate=str(item.get("substrate") or ""),
            status=str(item["status"]),
            required_additional_resources=_str_tuple(item.get("requiredAdditionalResources", [])),
            explanation=item.get("explanation"),
        )
        for item in raw["compatibilityRules"]
    )

    alternative_rules = tuple(
        AlternativeRuleSeed(
            from_material=str(item["from"]),
            to_material=str(item["to"]),
            alternative_type=str(item["type"]),
            recalculation_required=bool(item.get("recalculationRequired", False)),
            technology_change_required=bool(item.get("technologyChangeRequired", False)),
            condition=item.get("condition"),
        )
        for item in raw["alternativeRules"]
    )

    unit_conversions = tuple(
        UnitConversionRuleSeed(
            material_group=str(item["group"]),
            from_unit=str(item["from"]),
            to_unit=str(item["to"]),
            formula=str(item["formula"]),
            fallback=item.get("fallback"),
        )
        for item in raw["unitConversions"]
    )

    return MaterialKnowledgeSeedRegistry(
        version=str(raw["version"]),
        module=str(raw["module"]),
        purpose=str(raw["purpose"]),
        boundaries=MappingProxyType(dict(raw["boundaries"])),
        taxonomy=taxonomy,
        characteristic_schemas=characteristic_schemas,
        role_mappings=role_mappings,
        compatibility_rules=compatibility_rules,
        alternative_rules=alternative_rules,
        unit_conversions=unit_conversions,
    )


def validate_material_knowledge_seed(raw: Mapping[str, Any]) -> tuple[str, ...]:
    errors: list[str] = []
    for section in REQUIRED_SEED_SECTIONS:
        if section not in raw:
            errors.append(f"missing required section: {section}")
    if errors:
        return tuple(errors)

    _validate_type(raw, "version", str, errors)
    _validate_type(raw, "module", str, errors)
    _validate_type(raw, "purpose", str, errors)
    _validate_type(raw, "boundaries", dict, errors)
    _validate_type(raw, "taxonomy", list, errors)
    _validate_type(raw, "characteristicSchemas", dict, errors)
    _validate_type(raw, "roleMappings", list, errors)
    _validate_type(raw, "compatibilityRules", list, errors)
    _validate_type(raw, "alternativeRules", list, errors)
    _validate_type(raw, "unitConversions", list, errors)
    if errors:
        return tuple(errors)

    taxonomy_codes: set[str] = set()
    material_group_codes: set[str] = set()
    for index, item in enumerate(raw["taxonomy"]):
        if not isinstance(item, dict):
            errors.append(f"taxonomy[{index}] must be an object")
            continue
        _validate_required_str(item, "code", f"taxonomy[{index}]", errors)
        _validate_required_str(item, "name", f"taxonomy[{index}]", errors)
        children = item.get("children")
        if not isinstance(children, list) or not children or not all(isinstance(child, str) for child in children):
            errors.append(f"taxonomy[{index}].children must be a non-empty list of strings")
            continue
        code = item["code"]
        if code in taxonomy_codes:
            errors.append(f"duplicate taxonomy code: {code}")
        taxonomy_codes.add(code)
        material_group_codes.add(code)
        for child in children:
            material_group_codes.add(child)

    for group_code, schema in raw["characteristicSchemas"].items():
        if group_code not in material_group_codes:
            errors.append(f"characteristic schema references unknown material group: {group_code}")
        if not isinstance(schema, dict):
            errors.append(f"characteristicSchemas[{group_code}] must be an object")
            continue
        for key in ("required", "module2Required", "recommended"):
            value = schema.get(key)
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"characteristicSchemas[{group_code}].{key} must be a list of strings")
        if not schema.get("required"):
            errors.append(f"characteristicSchemas[{group_code}].required must not be empty")

    for group_code in KEY_MATERIAL_GROUPS:
        schema = raw["characteristicSchemas"].get(group_code)
        if not schema:
            errors.append(f"key material group is missing characteristic schema: {group_code}")
            continue
        if not schema.get("required"):
            errors.append(f"key material group has no required characteristics: {group_code}")

    for index, item in enumerate(raw["roleMappings"]):
        if not isinstance(item, dict):
            errors.append(f"roleMappings[{index}] must be an object")
            continue
        _validate_required_str(item, "materialGroup", f"roleMappings[{index}]", errors)
        roles = item.get("roles")
        if not isinstance(roles, list) or not roles or not all(isinstance(role, str) for role in roles):
            errors.append(f"roleMappings[{index}].roles must be a non-empty list of strings")

    for index, item in enumerate(raw["compatibilityRules"]):
        if not isinstance(item, dict):
            errors.append(f"compatibilityRules[{index}] must be an object")
            continue
        for key in ("context", "material", "status"):
            _validate_required_str(item, key, f"compatibilityRules[{index}]", errors)
        if item.get("status") not in {"allowed", "warning", "forbidden"}:
            errors.append(f"compatibilityRules[{index}].status must be allowed, warning, or forbidden")

    allowed_alternative_types = {
        "full_analog",
        "technical_alternative",
        "functional_alternative",
        "conditional_replacement",
        "forbidden_replacement",
    }
    for index, item in enumerate(raw["alternativeRules"]):
        if not isinstance(item, dict):
            errors.append(f"alternativeRules[{index}] must be an object")
            continue
        for key in ("from", "to", "type"):
            _validate_required_str(item, key, f"alternativeRules[{index}]", errors)
        if item.get("type") not in allowed_alternative_types:
            errors.append(
                f"alternativeRules[{index}].type must be one of: "
                f"{', '.join(sorted(allowed_alternative_types))}"
            )

    for index, item in enumerate(raw["unitConversions"]):
        if not isinstance(item, dict):
            errors.append(f"unitConversions[{index}] must be an object")
            continue
        for key in ("group", "from", "to", "formula"):
            _validate_required_str(item, key, f"unitConversions[{index}]", errors)

    return tuple(errors)


def _validate_type(raw: Mapping[str, Any], key: str, expected_type: type, errors: list[str]) -> None:
    if not isinstance(raw.get(key), expected_type):
        errors.append(f"{key} must be {expected_type.__name__}")


def _validate_required_str(raw: Mapping[str, Any], key: str, prefix: str, errors: list[str]) -> None:
    if not isinstance(raw.get(key), str) or not raw.get(key):
        errors.append(f"{prefix}.{key} must be a non-empty string")


def _str_tuple(value: Any) -> tuple[str, ...]:
    if not isinstance(value, list):
        return tuple()
    return tuple(str(item) for item in value)
