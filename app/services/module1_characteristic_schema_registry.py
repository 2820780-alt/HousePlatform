from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

from app.services.module1_material_seed_registry import (
    CharacteristicSchemaSeed,
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)


GROUP_CODE_ALIASES: Mapping[str, str] = {
    "gas_block": "aerated_concrete_block",
    "gazoblock": "aerated_concrete_block",
    "газоблок": "aerated_concrete_block",
    "gypsum_board": "gypsum_board_moisture_resistant",
    "gkl": "gypsum_board_moisture_resistant",
    "гкл": "gypsum_board_moisture_resistant",
    "concrete": "ready_mix_concrete",
    "бетон": "ready_mix_concrete",
    "dry_mix": "gypsum_plaster",
    "сухие_смеси": "gypsum_plaster",
    "primer": "deep_penetration_primer",
    "грунтовка": "deep_penetration_primer",
    "tile": "porcelain_tile",
    "плитка": "porcelain_tile",
    "roofing": "metal_tile",
    "кровля": "metal_tile",
    "lumber_board": "board",
    "доска": "board",
    "insulation": "mineral_wool_slab",
    "утеплитель": "mineral_wool_slab",
}


@dataclass(frozen=True)
class CharacteristicDefinition:
    code: str
    requirement: str
    expected_type: str | None = None
    expected_unit: str | None = None


@dataclass(frozen=True)
class CharacteristicSchemaView:
    group_code: str
    required: tuple[CharacteristicDefinition, ...]
    module2_required: tuple[CharacteristicDefinition, ...]
    recommended: tuple[CharacteristicDefinition, ...]

    def all_characteristic_codes(self) -> frozenset[str]:
        return frozenset(
            field.code
            for field in (
                self.required
                + self.module2_required
                + self.recommended
            )
        )


@dataclass(frozen=True)
class CharacteristicValidationIssue:
    field: str
    message: str
    expected: str | None = None
    actual: str | None = None


@dataclass(frozen=True)
class CharacteristicValidationReport:
    requested_group_code: str
    resolved_group_code: str | None
    schema_found: bool
    required_fields: tuple[str, ...]
    module2_required_fields: tuple[str, ...]
    recommended_fields: tuple[str, ...]
    provided_fields: tuple[str, ...]
    missing_required: tuple[str, ...]
    missing_module2_required: tuple[str, ...]
    missing_recommended: tuple[str, ...]
    type_errors: tuple[CharacteristicValidationIssue, ...]
    unit_errors: tuple[CharacteristicValidationIssue, ...]

    @property
    def is_valid(self) -> bool:
        return self.schema_found and not self.missing_required and not self.type_errors and not self.unit_errors


class CharacteristicSchemaRegistry:
    def __init__(self, seed_registry: MaterialKnowledgeSeedRegistry | None = None) -> None:
        self._seed_registry = seed_registry or get_material_knowledge_seed_registry()

    def resolve_group_code(self, group_code: str) -> str:
        return GROUP_CODE_ALIASES.get(group_code, group_code)

    def list_schema_groups(self) -> tuple[str, ...]:
        return tuple(sorted(self._seed_registry.characteristic_schemas.keys()))

    def has_schema(self, group_code: str) -> bool:
        return self.get_schema(group_code) is not None

    def get_schema(self, group_code: str) -> CharacteristicSchemaView | None:
        resolved_group_code = self.resolve_group_code(group_code)
        seed_schema = self._seed_registry.get_characteristic_schema(resolved_group_code)
        if seed_schema is None:
            return None
        return _schema_view_from_seed(seed_schema)

    def get_required_characteristics(self, group_code: str) -> tuple[str, ...]:
        schema = self.get_schema(group_code)
        return tuple(field.code for field in schema.required) if schema else tuple()

    def get_recommended_characteristics(self, group_code: str) -> tuple[str, ...]:
        schema = self.get_schema(group_code)
        return tuple(field.code for field in schema.recommended) if schema else tuple()

    def get_module2_required_characteristics(self, group_code: str) -> tuple[str, ...]:
        schema = self.get_schema(group_code)
        return tuple(field.code for field in schema.module2_required) if schema else tuple()

    def build_missing_required_report(
        self,
        group_code: str,
        characteristics: Mapping[str, Any] | None,
    ) -> CharacteristicValidationReport:
        return self.validate_characteristics(group_code, characteristics or {})

    def validate_characteristics(
        self,
        group_code: str,
        characteristics: Mapping[str, Any] | None,
    ) -> CharacteristicValidationReport:
        provided = dict(characteristics or {})
        provided_fields = tuple(sorted(provided.keys()))
        resolved_group_code = self.resolve_group_code(group_code)
        schema = self.get_schema(group_code)
        if schema is None:
            return CharacteristicValidationReport(
                requested_group_code=group_code,
                resolved_group_code=None,
                schema_found=False,
                required_fields=tuple(),
                module2_required_fields=tuple(),
                recommended_fields=tuple(),
                provided_fields=provided_fields,
                missing_required=tuple(),
                missing_module2_required=tuple(),
                missing_recommended=tuple(),
                type_errors=tuple(),
                unit_errors=tuple(),
            )

        required_fields = tuple(field.code for field in schema.required)
        module2_required_fields = tuple(field.code for field in schema.module2_required)
        recommended_fields = tuple(field.code for field in schema.recommended)

        missing_required = _missing_fields(required_fields, provided)
        missing_module2_required = _missing_fields(module2_required_fields, provided)
        missing_recommended = _missing_fields(recommended_fields, provided)
        type_errors = _validate_types(schema, provided)
        unit_errors = _validate_units(schema, provided)

        return CharacteristicValidationReport(
            requested_group_code=group_code,
            resolved_group_code=resolved_group_code,
            schema_found=True,
            required_fields=required_fields,
            module2_required_fields=module2_required_fields,
            recommended_fields=recommended_fields,
            provided_fields=provided_fields,
            missing_required=missing_required,
            missing_module2_required=missing_module2_required,
            missing_recommended=missing_recommended,
            type_errors=type_errors,
            unit_errors=unit_errors,
        )


def get_characteristic_schema_registry() -> CharacteristicSchemaRegistry:
    return CharacteristicSchemaRegistry()


def get_schema(group_code: str) -> CharacteristicSchemaView | None:
    return get_characteristic_schema_registry().get_schema(group_code)


def list_schema_groups() -> tuple[str, ...]:
    return get_characteristic_schema_registry().list_schema_groups()


def get_required_characteristics(group_code: str) -> tuple[str, ...]:
    return get_characteristic_schema_registry().get_required_characteristics(group_code)


def has_schema(group_code: str) -> bool:
    return get_characteristic_schema_registry().has_schema(group_code)


def validate_characteristics(
    group_code: str,
    characteristics: Mapping[str, Any] | None,
) -> CharacteristicValidationReport:
    return get_characteristic_schema_registry().validate_characteristics(group_code, characteristics)


def build_missing_required_report(
    group_code: str,
    characteristics: Mapping[str, Any] | None,
) -> CharacteristicValidationReport:
    return get_characteristic_schema_registry().build_missing_required_report(group_code, characteristics)


def _schema_view_from_seed(seed_schema: CharacteristicSchemaSeed) -> CharacteristicSchemaView:
    return CharacteristicSchemaView(
        group_code=seed_schema.material_group,
        required=tuple(
            CharacteristicDefinition(code=code, requirement="required")
            for code in seed_schema.required
        ),
        module2_required=tuple(
            CharacteristicDefinition(code=code, requirement="module2_required")
            for code in seed_schema.module2_required
        ),
        recommended=tuple(
            CharacteristicDefinition(code=code, requirement="recommended")
            for code in seed_schema.recommended
        ),
    )


def _missing_fields(fields: tuple[str, ...], characteristics: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(field for field in fields if _is_missing(characteristics.get(field)))


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, set, dict)):
        return not value
    return False


def _validate_types(
    schema: CharacteristicSchemaView,
    characteristics: Mapping[str, Any],
) -> tuple[CharacteristicValidationIssue, ...]:
    issues: list[CharacteristicValidationIssue] = []
    for field in _fields_with_constraints(schema):
        if not field.expected_type or field.code not in characteristics:
            continue
        actual_value = _extract_value(characteristics[field.code])
        if _is_missing(actual_value):
            continue
        if not _matches_expected_type(actual_value, field.expected_type):
            issues.append(
                CharacteristicValidationIssue(
                    field=field.code,
                    message="Characteristic value has invalid type.",
                    expected=field.expected_type,
                    actual=type(actual_value).__name__,
                )
            )
    return tuple(issues)


def _validate_units(
    schema: CharacteristicSchemaView,
    characteristics: Mapping[str, Any],
) -> tuple[CharacteristicValidationIssue, ...]:
    issues: list[CharacteristicValidationIssue] = []
    for field in _fields_with_constraints(schema):
        if not field.expected_unit or field.code not in characteristics:
            continue
        actual_unit = _extract_unit(characteristics[field.code])
        if actual_unit and actual_unit != field.expected_unit:
            issues.append(
                CharacteristicValidationIssue(
                    field=field.code,
                    message="Characteristic unit does not match schema.",
                    expected=field.expected_unit,
                    actual=actual_unit,
                )
            )
    return tuple(issues)


def _fields_with_constraints(schema: CharacteristicSchemaView) -> tuple[CharacteristicDefinition, ...]:
    return schema.required + schema.module2_required + schema.recommended


def _extract_value(raw_value: Any) -> Any:
    if isinstance(raw_value, Mapping) and "value" in raw_value:
        return raw_value["value"]
    return raw_value


def _extract_unit(raw_value: Any) -> str | None:
    if isinstance(raw_value, Mapping):
        unit = raw_value.get("unit")
        return str(unit) if unit else None
    return None


def _matches_expected_type(value: Any, expected_type: str) -> bool:
    normalized_type = expected_type.lower()
    if normalized_type in {"number", "decimal", "float", "integer"}:
        return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)
    if normalized_type in {"text", "string"}:
        return isinstance(value, str)
    if normalized_type == "boolean":
        return isinstance(value, bool)
    if normalized_type == "json":
        return isinstance(value, (dict, list))
    return True
