from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


DEFAULT_WORK_CATALOG_SEED_PATH = (
    Path(__file__).resolve().parents[2] / "src/modules/module1/seeds/work_catalog_seed.json"
)

REQUIRED_WORK_CATALOG_SECTIONS = (
    "version",
    "module",
    "domain",
    "rules",
    "units",
    "groups",
    "works",
)

ALLOWED_APPLIES_TO = frozenset({"apartment", "private_house", "both"})

FORBIDDEN_WORK_ITEM_FIELDS = frozenset(
    {
        "price",
        "price_from",
        "price_to",
        "cost",
        "cost_from",
        "cost_to",
        "provider",
        "provider_id",
        "contractor",
        "contractor_id",
        "executor",
        "executor_id",
        "contact",
        "contacts",
        "contact_phone",
        "contact_email",
    }
)


class WorkCatalogError(ValueError):
    pass


@dataclass(frozen=True)
class WorkGroup:
    work_group: str
    work_category: str


@dataclass(frozen=True)
class WorkItem:
    work_code: str
    work_group: str
    work_category: str
    work_name: str
    default_unit: str
    allowed_units: tuple[str, ...]
    is_range_allowed: bool
    applies_to: str
    module2_usage_hint: str | None = None
    module5_usage_hint: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class WorkCatalogValidationReport:
    is_valid: bool
    errors: tuple[str, ...]


@dataclass(frozen=True)
class WorkCatalogSummary:
    version: str
    module: str
    domain: str
    group_count: int
    work_count: int
    unit_count: int
    applies_to: tuple[str, ...]
    range_allowed_count: int


@dataclass(frozen=True)
class WorkCatalogRegistry:
    version: str
    module: str
    domain: str
    rules: Mapping[str, Any]
    units: Mapping[str, str]
    groups: tuple[WorkGroup, ...]
    works: tuple[WorkItem, ...]

    def list_work_items(self) -> tuple[WorkItem, ...]:
        return self.works

    def get_work_item(self, work_code: str) -> WorkItem | None:
        return next((work for work in self.works if work.work_code == work_code), None)

    def list_work_groups(self) -> tuple[WorkGroup, ...]:
        return self.groups

    def list_work_by_group(self, work_group: str) -> tuple[WorkItem, ...]:
        return tuple(work for work in self.works if work.work_group == work_group)

    def list_work_by_applies_to(self, applies_to: str) -> tuple[WorkItem, ...]:
        if applies_to not in ALLOWED_APPLIES_TO:
            return tuple()
        if applies_to == "both":
            return tuple(work for work in self.works if work.applies_to == "both")
        return tuple(work for work in self.works if work.applies_to in {applies_to, "both"})

    def get_allowed_units(self, work_code: str) -> tuple[str, ...]:
        work = self.get_work_item(work_code)
        return work.allowed_units if work else tuple()

    def is_range_allowed(self, work_code: str) -> bool:
        work = self.get_work_item(work_code)
        return bool(work and work.is_range_allowed)

    def build_work_catalog_summary(self) -> WorkCatalogSummary:
        return WorkCatalogSummary(
            version=self.version,
            module=self.module,
            domain=self.domain,
            group_count=len(self.groups),
            work_count=len(self.works),
            unit_count=len(self.units),
            applies_to=tuple(sorted({work.applies_to for work in self.works})),
            range_allowed_count=sum(1 for work in self.works if work.is_range_allowed),
        )


def load_work_catalog_seed(path: Path | str = DEFAULT_WORK_CATALOG_SEED_PATH) -> WorkCatalogRegistry:
    seed_path = Path(path)
    if not seed_path.exists():
        raise WorkCatalogError(f"Module 1 work catalog seed not found: {seed_path}")
    try:
        raw = json.loads(seed_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkCatalogError(f"Module 1 work catalog seed is not valid JSON: {exc}") from exc
    return build_work_catalog_registry(raw)


@lru_cache(maxsize=1)
def get_work_catalog_registry() -> WorkCatalogRegistry:
    return load_work_catalog_seed(DEFAULT_WORK_CATALOG_SEED_PATH)


def build_work_catalog_registry(raw: Mapping[str, Any]) -> WorkCatalogRegistry:
    errors = validate_work_catalog(raw).errors
    if errors:
        raise WorkCatalogError("; ".join(errors))

    groups = tuple(
        WorkGroup(
            work_group=str(item["work_group"]),
            work_category=str(item["work_category"]),
        )
        for item in raw["groups"]
    )
    works = tuple(validate_work_item(item) for item in raw["works"])

    return WorkCatalogRegistry(
        version=str(raw["version"]),
        module=str(raw["module"]),
        domain=str(raw["domain"]),
        rules=MappingProxyType(dict(raw["rules"])),
        units=MappingProxyType({str(key): str(value) for key, value in raw["units"].items()}),
        groups=groups,
        works=works,
    )


def list_work_items() -> tuple[WorkItem, ...]:
    return get_work_catalog_registry().list_work_items()


def get_work_item(work_code: str) -> WorkItem | None:
    return get_work_catalog_registry().get_work_item(work_code)


def list_work_groups() -> tuple[WorkGroup, ...]:
    return get_work_catalog_registry().list_work_groups()


def list_work_by_group(work_group: str) -> tuple[WorkItem, ...]:
    return get_work_catalog_registry().list_work_by_group(work_group)


def list_work_by_applies_to(applies_to: str) -> tuple[WorkItem, ...]:
    return get_work_catalog_registry().list_work_by_applies_to(applies_to)


def get_allowed_units(work_code: str) -> tuple[str, ...]:
    return get_work_catalog_registry().get_allowed_units(work_code)


def is_range_allowed(work_code: str) -> bool:
    return get_work_catalog_registry().is_range_allowed(work_code)


def build_work_catalog_summary() -> WorkCatalogSummary:
    return get_work_catalog_registry().build_work_catalog_summary()


def validate_work_catalog(raw: Mapping[str, Any] | None = None) -> WorkCatalogValidationReport:
    if raw is None:
        seed_path = DEFAULT_WORK_CATALOG_SEED_PATH
        if not seed_path.exists():
            return WorkCatalogValidationReport(
                is_valid=False,
                errors=(f"Module 1 work catalog seed not found: {seed_path}",),
            )
        try:
            raw = json.loads(seed_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            return WorkCatalogValidationReport(is_valid=False, errors=(f"invalid JSON: {exc}",))

    errors: list[str] = []
    for section in REQUIRED_WORK_CATALOG_SECTIONS:
        if section not in raw:
            errors.append(f"missing required section: {section}")
    if errors:
        return WorkCatalogValidationReport(is_valid=False, errors=tuple(errors))

    _validate_type(raw, "version", str, errors)
    _validate_type(raw, "module", str, errors)
    _validate_type(raw, "domain", str, errors)
    _validate_type(raw, "rules", dict, errors)
    _validate_type(raw, "units", dict, errors)
    _validate_type(raw, "groups", list, errors)
    _validate_type(raw, "works", list, errors)
    if errors:
        return WorkCatalogValidationReport(is_valid=False, errors=tuple(errors))

    units = set(str(unit) for unit in raw["units"].keys())
    group_codes: set[str] = set()
    for index, item in enumerate(raw["groups"]):
        if not isinstance(item, dict):
            errors.append(f"groups[{index}] must be an object")
            continue
        _validate_required_str(item, "work_group", f"groups[{index}]", errors)
        _validate_required_str(item, "work_category", f"groups[{index}]", errors)
        work_group = item.get("work_group")
        if work_group in group_codes:
            errors.append(f"duplicate work group: {work_group}")
        group_codes.add(str(work_group))

    work_codes: set[str] = set()
    applies_to_values: set[str] = set()
    for index, item in enumerate(raw["works"]):
        if not isinstance(item, dict):
            errors.append(f"works[{index}] must be an object")
            continue
        item_errors = _validate_work_item_shape(item, units, group_codes, prefix=f"works[{index}]")
        errors.extend(item_errors)
        work_code = item.get("work_code")
        if isinstance(work_code, str):
            if work_code in work_codes:
                errors.append(f"duplicate work code: {work_code}")
            work_codes.add(work_code)
        applies_to = item.get("applies_to")
        if isinstance(applies_to, str):
            applies_to_values.add(applies_to)

    for required_applies_to in ALLOWED_APPLIES_TO:
        if required_applies_to not in applies_to_values:
            errors.append(f"work catalog does not cover applies_to: {required_applies_to}")

    return WorkCatalogValidationReport(is_valid=not errors, errors=tuple(errors))


def validate_work_item(work_item: Mapping[str, Any]) -> WorkItem:
    errors = _validate_work_item_shape(work_item, units=None, group_codes=None, prefix="work_item")
    if errors:
        raise WorkCatalogError("; ".join(errors))
    return WorkItem(
        work_code=str(work_item["work_code"]),
        work_group=str(work_item["work_group"]),
        work_category=str(work_item["work_category"]),
        work_name=str(work_item["work_name"]),
        default_unit=str(work_item["default_unit"]),
        allowed_units=_str_tuple(work_item["allowed_units"]),
        is_range_allowed=bool(work_item["is_range_allowed"]),
        applies_to=str(work_item["applies_to"]),
        module2_usage_hint=_optional_str(work_item.get("module2_usage_hint")),
        module5_usage_hint=_optional_str(work_item.get("module5_usage_hint")),
        description=_optional_str(work_item.get("description")),
    )


def _validate_work_item_shape(
    work_item: Mapping[str, Any],
    units: set[str] | None,
    group_codes: set[str] | None,
    prefix: str,
) -> tuple[str, ...]:
    errors: list[str] = []
    for key in (
        "work_code",
        "work_group",
        "work_category",
        "work_name",
        "default_unit",
        "applies_to",
    ):
        _validate_required_str(work_item, key, prefix, errors)

    if not isinstance(work_item.get("allowed_units"), list) or not work_item.get("allowed_units"):
        errors.append(f"{prefix}.allowed_units must be a non-empty list")
    elif not all(isinstance(unit, str) and unit for unit in work_item["allowed_units"]):
        errors.append(f"{prefix}.allowed_units must contain only non-empty strings")

    if not isinstance(work_item.get("is_range_allowed"), bool):
        errors.append(f"{prefix}.is_range_allowed must be bool")

    forbidden_fields = sorted(FORBIDDEN_WORK_ITEM_FIELDS.intersection(work_item.keys()))
    if forbidden_fields:
        errors.append(f"{prefix} contains forbidden price/provider/contact fields: {', '.join(forbidden_fields)}")

    default_unit = work_item.get("default_unit")
    allowed_units = work_item.get("allowed_units")
    if isinstance(default_unit, str) and isinstance(allowed_units, list) and default_unit not in allowed_units:
        errors.append(f"{prefix}.default_unit must be included in allowed_units")

    if units is not None and isinstance(allowed_units, list):
        for unit in allowed_units:
            if isinstance(unit, str) and unit not in units:
                errors.append(f"{prefix}.allowed_units references unknown unit: {unit}")

    work_group = work_item.get("work_group")
    if group_codes is not None and isinstance(work_group, str) and work_group not in group_codes:
        errors.append(f"{prefix}.work_group references unknown group: {work_group}")

    applies_to = work_item.get("applies_to")
    if applies_to not in ALLOWED_APPLIES_TO:
        errors.append(f"{prefix}.applies_to must be one of: {', '.join(sorted(ALLOWED_APPLIES_TO))}")

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


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)
