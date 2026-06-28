from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


MODULE_LIFECYCLE_STATUSES: tuple[str, ...] = (
    "PLANNED",
    "DRAFT",
    "ACTIVE",
    "DISABLED",
    "DEPRECATED",
    "ARCHIVED",
    "MERGED",
)
MODULE_USER_HIDDEN_STATUSES: set[str] = {
    "PLANNED",
    "DRAFT",
    "DISABLED",
    "DEPRECATED",
    "ARCHIVED",
    "MERGED",
}
MODULE_TERMINAL_STATUSES: set[str] = {"DEPRECATED", "ARCHIVED", "MERGED"}
MODULE_ALIAS_STATUSES: set[str] = {"DEPRECATED", "MERGED"}
MODULE_REDIRECT_STATUSES: set[str] = {"DEPRECATED", "MERGED"}
MODULE_ACTIVE_STATUSES: set[str] = {"ACTIVE"}


@dataclass(frozen=True)
class ModuleLifecycleRule:
    status: str
    title: str
    description: str
    userVisible: bool
    active: bool
    allowsWidgets: bool
    preservesHistory: bool
    requiresRedirect: bool = False
    requiresMergedIntoModuleCode: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


MODULE_LIFECYCLE_RULES: dict[str, ModuleLifecycleRule] = {
    "PLANNED": ModuleLifecycleRule(
        status="PLANNED",
        title="Планируется",
        description="Будущий модуль. Обычным пользователям не виден.",
        userVisible=False,
        active=False,
        allowsWidgets=False,
        preservesHistory=True,
    ),
    "DRAFT": ModuleLifecycleRule(
        status="DRAFT",
        title="Черновик",
        description="Модуль проектируется или частично готовится. Обычным пользователям не виден.",
        userVisible=False,
        active=False,
        allowsWidgets=False,
        preservesHistory=True,
    ),
    "ACTIVE": ModuleLifecycleRule(
        status="ACTIVE",
        title="Работает",
        description="Модуль работает и может отображаться пользователю при наличии прав.",
        userVisible=True,
        active=True,
        allowsWidgets=True,
        preservesHistory=True,
    ),
    "DISABLED": ModuleLifecycleRule(
        status="DISABLED",
        title="Отключен",
        description="Модуль временно отключен и не должен показываться как активный.",
        userVisible=False,
        active=False,
        allowsWidgets=False,
        preservesHistory=True,
    ),
    "DEPRECATED": ModuleLifecycleRule(
        status="DEPRECATED",
        title="Устаревает",
        description="Модуль устаревает. Ссылки, история и alias сохраняются.",
        userVisible=False,
        active=False,
        allowsWidgets=False,
        preservesHistory=True,
        requiresRedirect=True,
    ),
    "ARCHIVED": ModuleLifecycleRule(
        status="ARCHIVED",
        title="Архив",
        description="Модуль скрыт из интерфейса, но история сохраняется.",
        userVisible=False,
        active=False,
        allowsWidgets=False,
        preservesHistory=True,
    ),
    "MERGED": ModuleLifecycleRule(
        status="MERGED",
        title="Объединен",
        description="Модуль объединен с другим модулем, не показывается отдельно, но сохраняет alias/redirect.",
        userVisible=False,
        active=False,
        allowsWidgets=False,
        preservesHistory=True,
        requiresRedirect=True,
        requiresMergedIntoModuleCode=True,
    ),
}


def normalize_module_status(status: str | None) -> str | None:
    if not status:
        return None
    normalized = str(status).upper()
    return normalized if normalized in MODULE_LIFECYCLE_STATUSES else None


def get_module_lifecycle_rules() -> list[dict[str, Any]]:
    return [MODULE_LIFECYCLE_RULES[status].to_dict() for status in MODULE_LIFECYCLE_STATUSES]


def get_module_lifecycle_rule(status: str | None) -> ModuleLifecycleRule | None:
    normalized = normalize_module_status(status)
    return MODULE_LIFECYCLE_RULES.get(normalized) if normalized else None


def is_module_user_visible_status(status: str | None) -> bool:
    rule = get_module_lifecycle_rule(status)
    return bool(rule and rule.userVisible)


def is_module_hidden_from_users(status: str | None) -> bool:
    normalized = normalize_module_status(status)
    return normalized in MODULE_USER_HIDDEN_STATUSES


def is_module_terminal_status(status: str | None) -> bool:
    normalized = normalize_module_status(status)
    return normalized in MODULE_TERMINAL_STATUSES


def apply_module_lifecycle_state(
    module: Any,
    status: str,
    *,
    visible_flags: dict[str, bool] | None = None,
) -> Any:
    normalized = normalize_module_status(status)
    if not normalized:
        raise ValueError("Unsupported module lifecycle status.")
    rule = MODULE_LIFECYCLE_RULES[normalized]
    _set_value(module, "status", normalized)
    _set_value(module, "is_active", rule.active)
    if rule.userVisible:
        flags = visible_flags or {}
        _set_value(module, "is_visible_in_sidebar", bool(flags.get("sidebar", True)))
        _set_value(module, "is_visible_on_dashboard", bool(flags.get("dashboard", True)))
        _set_value(module, "is_visible_on_atom_map", bool(flags.get("atomMap", True)))
        _set_value(module, "is_available_for_widgets", bool(flags.get("widgets", rule.allowsWidgets)))
    else:
        _set_value(module, "is_visible_in_sidebar", False)
        _set_value(module, "is_visible_on_dashboard", False)
        _set_value(module, "is_visible_on_atom_map", False)
        _set_value(module, "is_available_for_widgets", False)
    return module


def module_lifecycle_validation_errors(module: Any, target_status: str | None) -> list[str]:
    normalized = normalize_module_status(target_status)
    if not normalized:
        return ["Unsupported module lifecycle status."]
    rule = MODULE_LIFECYCLE_RULES[normalized]
    errors: list[str] = []
    module_code = _get_value(module, "module_code")
    canonical_code = _get_value(module, "canonical_module_code")
    merged_into = _get_value(module, "merged_into_module_code")
    redirect_route = _get_value(module, "redirect_route")

    if rule.requiresMergedIntoModuleCode and not merged_into:
        errors.append("MERGED status requires merged_into_module_code.")
    if rule.requiresRedirect and not (redirect_route or merged_into or canonical_code != module_code):
        errors.append("Lifecycle alias status requires redirectRoute, merged target or canonical alias.")
    if normalized == "ACTIVE" and canonical_code and canonical_code != module_code:
        errors.append("Legacy/alias module cannot become ACTIVE.")
    return errors


def can_transition_module_lifecycle(module: Any, target_status: str | None) -> bool:
    return not module_lifecycle_validation_errors(module, target_status)


def can_physically_delete_module(module: Any, dependencies: dict[str, Any] | None = None) -> bool:
    if _bool_value(module, "is_system"):
        return False
    if _get_value(module, "legacy_codes") or _get_value(module, "merged_into_module_code"):
        return False
    for items in (dependencies or {}).values():
        if _dependency_count(items) > 0:
            return False
    return True


def module_lifecycle_summary(module: Any) -> dict[str, Any]:
    rule = get_module_lifecycle_rule(_get_value(module, "status"))
    return {
        "status": _get_value(module, "status"),
        "rule": rule.to_dict() if rule else None,
        "isUserVisible": bool(rule and rule.userVisible and _bool_value(module, "is_active")),
        "preservesHistory": bool(rule and rule.preservesHistory),
        "physicalDeleteForbidden": not can_physically_delete_module(module),
    }


def _dependency_count(items: Any) -> int:
    if not items:
        return 0
    if isinstance(items, list):
        if len(items) == 1 and isinstance(items[0], dict) and "count" in items[0]:
            return int(items[0]["count"])
        return len(items)
    return 1


def _get_value(source: Any, field_name: str) -> Any:
    if source is None:
        return None
    if isinstance(source, dict):
        return source.get(field_name)
    return getattr(source, field_name, None)


def _set_value(target: Any, field_name: str, value: Any) -> None:
    if isinstance(target, dict):
        target[field_name] = value
    else:
        setattr(target, field_name, value)


def _bool_value(source: Any, field_name: str) -> bool:
    return bool(_get_value(source, field_name))
