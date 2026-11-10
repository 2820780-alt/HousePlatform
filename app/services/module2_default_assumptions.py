from __future__ import annotations

import uuid
from copy import deepcopy
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module2_technology import Technology, TechnologyDefaultAssumption
from app.services.audit_service import log_event


class DefaultAssumptionError(ValueError):
    pass


# Historical defaults remain stored for audit, but the current foundation
# specification explicitly requires these inputs from the object or system.
FOUNDATION_EXPLICIT_INPUTS = frozenset({
    ("FND_STRIP_MONOLITHIC_RC", "FOUNDATION_DEPTH_MM"),
    ("FND_STRIP_PRECAST_FBS_FL", "FOUNDATION_DEPTH_MM"),
    ("FND_SLAB_RIBBED_RC", "SLAB_THICKNESS_MM"),
    ("FND_SLAB_RIBBED_RC", "RIB_HEIGHT_MM"),
    ("FND_SLAB_USHP", "SLAB_THICKNESS_MM"),
    ("FND_UFF", "SLAB_THICKNESS_MM"),
    ("FND_PILE_BORED_RC", "PILE_LENGTH_MM"),
    ("FND_PILE_BORED_RC", "PILE_DIAMETER_MM"),
    ("FND_PILE_GRILLAGE", "GRILLAGE_WIDTH_MM"),
    ("FND_PILE_GRILLAGE", "GRILLAGE_HEIGHT_MM"),
    ("FND_COLUMN_CONCRETE_RC", "COLUMN_WIDTH_MM"),
    ("FND_COLUMN_CONCRETE_RC", "FOUNDATION_DEPTH_MM"),
    ("FND_BASEMENT_WALL_MONOLITHIC", "WALL_HEIGHT_MM"),
    ("FND_SUBSTRUCTURE_WATERPROOFING_COATING", "COATING_THICKNESS_MM"),
    ("FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE", "MEMBRANE_THICKNESS_MM"),
})


def requires_explicit_foundation_input(technology: Technology, assumption: TechnologyDefaultAssumption) -> bool:
    return (technology.technology_code, assumption.parameter_code) in FOUNDATION_EXPLICIT_INPUTS


def may_use_default(technology: Technology, assumption: TechnologyDefaultAssumption) -> bool:
    return bool(assumption.auto_fallback) and not requires_explicit_foundation_input(technology, assumption)


def active_defaults(technology: Technology) -> tuple[TechnologyDefaultAssumption, ...]:
    return tuple(sorted(
        (item for item in technology.default_assumptions if item.status == "ACTIVE"),
        key=lambda item: (item.parameter_code, item.assumption_code),
    ))


def _value(assumption: TechnologyDefaultAssumption, value: Any) -> Any:
    if assumption.value_type == "NUMBER":
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError) as exc:
            raise DefaultAssumptionError("Ожидается число.") from exc
        if not number.is_finite():
            raise DefaultAssumptionError("Число должно быть конечным.")
        bounds = assumption.allowed_values or {}
        if bounds.get("positive") and number <= 0:
            raise DefaultAssumptionError("Значение должно быть положительным.")
        if bounds.get("integer") and number != number.to_integral_value():
            raise DefaultAssumptionError("Значение должно быть целым числом.")
        if "min" in bounds and number < Decimal(str(bounds["min"])):
            raise DefaultAssumptionError("Значение ниже допустимого диапазона.")
        if "max" in bounds and number > Decimal(str(bounds["max"])):
            raise DefaultAssumptionError("Значение выше допустимого диапазона.")
        return str(number)
    if assumption.value_type == "BOOLEAN":
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            value = value.lower() == "true"
        if type(value) is not bool:
            raise DefaultAssumptionError("Ожидается логическое значение.")
        return value
    if assumption.value_type in {"ENUM", "MATERIAL", "MATERIAL_CLASS"}:
        allowed = (assumption.allowed_values or {}).get("values", [])
        if assumption.value_type in {"MATERIAL", "MATERIAL_CLASS"}:
            allowed = (assumption.allowed_values or {}).get("material_ids" if assumption.value_type == "MATERIAL" else "category_ids", [])
        if str(value) not in {str(item) for item in allowed}:
            raise DefaultAssumptionError("Значение не входит в допустимые варианты технологии.")
        if assumption.value_type == "MATERIAL_CLASS":
            requirement = assumption.material_requirement
            if requirement is None or str(requirement.material_category_id) != str(value):
                raise DefaultAssumptionError("Класс материала не соответствует требованию технологии M1.")
        return str(value)
    if assumption.value_type == "TEXT":
        if not isinstance(value, str) or not value.strip() or len(value) > 500:
            raise DefaultAssumptionError("Текст должен содержать от 1 до 500 символов.")
        return value.strip()
    raise DefaultAssumptionError("Неизвестный тип значения по умолчанию.")


def resolve_default_assumptions(
    technology: Technology,
    *,
    project_values: Mapping[str, Any] | None = None,
    user_overrides: Mapping[str, Any] | None = None,
) -> tuple[dict[str, Any], ...]:
    """Read-only resolution; callers persist a snapshot themselves if required."""
    project_values = project_values or {}
    user_overrides = user_overrides or {}
    result = []
    for item in active_defaults(technology):
        if item.material_requirement_id and not any(
            requirement.id == item.material_requirement_id for requirement in technology.requirements
        ):
            raise DefaultAssumptionError("Требование материала относится к другой технологии.")
        code = item.parameter_code
        project_value = project_values.get(code)
        override = user_overrides.get(code)
        default = _value(item, item.default_value["value"])
        if override is not None:
            resolved, source = _value(item, override), "USER_OVERRIDE"
        elif project_value is not None:
            resolved, source = _value(item, project_value), "PROJECT_VALUE"
        elif may_use_default(technology, item):
            resolved, source = default, "M2_DEFAULT"
        else:
            resolved, source = None, "UNRESOLVED"
        result.append({
            "assumption_code": item.assumption_code,
            "assumption_revision": item.revision,
            "parameter_code": code,
            "name_ru": item.name_ru,
            "value_type": item.value_type,
            "unit": item.unit,
            "project_value": project_value,
            "user_override": override,
            "default_value": default,
            "resolved_value": resolved,
            "source": source,
            "source_kind": item.source_kind,
            "warning_level": item.warning_level if source == "M2_DEFAULT" else (
                "WARNING" if source == "UNRESOLVED" and requires_explicit_foundation_input(technology, item) else None),
            "warning_text": item.warning_text if source == "M2_DEFAULT" else (
                "Требуется значение объекта или выбранной системы."
                if source == "UNRESOLVED" and requires_explicit_foundation_input(technology, item) else None),
            "allowed_values_strategy": item.allowed_values_strategy,
            "allowed_values": deepcopy(item.allowed_values),
            "allowed_alternatives": tuple(
                (item.allowed_values or {}).get(
                    "values" if item.value_type == "ENUM" else
                    "category_ids" if item.value_type == "MATERIAL_CLASS" else
                    "material_ids" if item.value_type == "MATERIAL" else "none", ()
                )
            ),
            "technology_code": technology.technology_code,
            "technology_revision": technology.revision,
        })
    return tuple(result)


async def revise_default_assumption(
    db: AsyncSession,
    technology: Technology,
    *,
    assumption_code: str,
    value: Any,
    actor_user_id: uuid.UUID | None,
) -> TechnologyDefaultAssumption:
    if technology.status == "ARCHIVED":
        raise DefaultAssumptionError("Архивную технологию изменять нельзя.")
    if actor_user_id is None:
        raise DefaultAssumptionError("Для изменения глобального значения нужен пользователь.")
    current = await db.scalar(
        select(TechnologyDefaultAssumption)
        .where(
            TechnologyDefaultAssumption.technology_id == technology.id,
            TechnologyDefaultAssumption.assumption_code == assumption_code,
            TechnologyDefaultAssumption.status == "ACTIVE",
        )
        .with_for_update()
    )
    if current is None:
        raise DefaultAssumptionError("Действующее значение по умолчанию не найдено.")
    parsed = _value(current, value)
    if parsed == _value(current, current.default_value["value"]):
        return current
    current.status = "SUPERSEDED"
    revised = TechnologyDefaultAssumption(
        id=uuid.uuid4(), technology_id=technology.id,
        assumption_code=current.assumption_code, revision=current.revision + 1,
        parameter_code=current.parameter_code, name_ru=current.name_ru,
        value_type=current.value_type, unit=current.unit,
        default_value={"value": parsed}, source_kind="PLATFORM_ASSUMPTION",
        applicability=deepcopy(current.applicability), auto_fallback=current.auto_fallback,
        warning_level=current.warning_level, warning_text=current.warning_text,
        allowed_values_strategy=current.allowed_values_strategy,
        allowed_values=deepcopy(current.allowed_values),
        material_requirement_id=current.material_requirement_id,
        evidence_reference_id=None, status="ACTIVE", created_by_user_id=actor_user_id,
    )
    db.add(revised)
    await db.flush()
    await log_event(
        db, event_type="MODULE2_DEFAULT_REVISED", entity_type="TechnologyDefaultAssumption",
        entity_id=revised.id, user_id=actor_user_id,
        details={"technology_id": str(technology.id), "assumption_code": assumption_code,
                 "old_revision": current.revision, "new_revision": revised.revision,
                 "old_value": current.default_value, "new_value": revised.default_value},
    )
    return revised
