from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Iterable, Mapping


CANONICAL_UPDATE_FIELDS = frozenset(
    {
        "canonical_name",
        "category_id",
        "subcategory_id",
        "material_type_id",
        "manufacturer_id",
        "brand_id",
        "base_unit_id",
        "article",
        "brand",
        "manufacturer",
        "description",
        "status",
    }
)

BLOCKED_UPDATE_FIELDS = frozenset(
    {
        "id",
        "material_id",
        "raw_payload",
        "raw_source",
        "source_payload",
        "source_task_result",
        "catalog_products",
        "supplier_prices",
        "documents",
        "quality_issues",
        "created_at",
        "updated_at",
    }
)


@dataclass(frozen=True)
class MaterialCharacteristicView:
    name: str
    value: Any
    unit: str | None = None
    source_ref: Mapping[str, Any] | None = None
    confidence: Decimal | None = None
    verification_status: str | None = None


@dataclass(frozen=True)
class MaterialQualitySummary:
    status: str
    open_issues: int
    critical_issues: int
    warning_issues: int
    issues: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MaterialEvidenceSummary:
    document_count: int
    source_ref_count: int
    documents: tuple[Mapping[str, Any], ...]
    source_refs: tuple[Mapping[str, Any], ...]
    moderation_preview_refs: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MaterialCanonicalView:
    material_id: str | None
    canonical_name: str
    category: Mapping[str, Any] | None
    subcategory: Mapping[str, Any] | None
    group: Mapping[str, Any] | None
    characteristics: tuple[MaterialCharacteristicView, ...]
    technical_profile_hints: Mapping[str, Any]
    evidence: MaterialEvidenceSummary
    supplier_price_refs: tuple[Mapping[str, Any], ...]
    moderation_status: str
    quality: MaterialQualitySummary
    source_provenance: Mapping[str, Any]
    status: str | None
    warnings: tuple[str, ...]
    created_at: str | None
    updated_at: str | None


@dataclass(frozen=True)
class MaterialCanonicalUpdateValidation:
    is_valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    sanitized_payload: Mapping[str, Any]
    allowed_fields: tuple[str, ...]
    blocked_fields: tuple[str, ...]


@dataclass(frozen=True)
class MaterialCanonicalUpdatePlan:
    material_id: str | None
    human_readable_summary: str
    sanitized_payload: Mapping[str, Any]
    operations_preview: tuple[str, ...]
    warnings: tuple[str, ...]
    requires_manual_save: bool
    no_side_effects: bool
    source_preview_only: bool


def get_canonical_material(
    material_id: Any,
    *,
    materials: Iterable[Any] | None = None,
) -> MaterialCanonicalView | None:
    for material in materials or ():
        if _string_id(_value(material, "id")) == str(material_id):
            return build_canonical_material_view(material)
    return None


def list_canonical_materials(
    filters: Mapping[str, Any] | None = None,
    *,
    materials: Iterable[Any] | None = None,
) -> tuple[MaterialCanonicalView, ...]:
    filters = filters or {}
    views = [build_canonical_material_view(material) for material in materials or ()]
    return tuple(view for view in views if _matches_filters(view, filters))


def build_canonical_material_view(
    material: Any,
    *,
    moderation_preview_refs: Iterable[Mapping[str, Any]] | None = None,
) -> MaterialCanonicalView:
    characteristics = build_material_characteristics_view(material)
    quality = build_material_quality_summary(material)
    evidence = build_material_evidence_summary(material, moderation_preview_refs=moderation_preview_refs)
    supplier_price_refs = _supplier_price_refs(material)
    warnings = _view_warnings(material, characteristics, evidence, quality)
    return MaterialCanonicalView(
        material_id=_string_id(_value(material, "id")),
        canonical_name=str(_value(material, "canonical_name") or ""),
        category=_category_ref(_value(material, "category"), _value(material, "category_id")),
        subcategory=_category_ref(_value(material, "subcategory"), _value(material, "subcategory_id")),
        group=_material_type_ref(_value(material, "material_type"), _value(material, "material_type_id")),
        characteristics=characteristics,
        technical_profile_hints=_technical_profile_hints(material, characteristics),
        evidence=evidence,
        supplier_price_refs=supplier_price_refs,
        moderation_status=_moderation_status(material, quality),
        quality=quality,
        source_provenance={
            "canonicalBase": "Material",
            "rawDataIsCanonical": False,
            "sourceDetailsLocation": "evidence",
        },
        status=_enum_value(_value(material, "status")),
        warnings=warnings,
        created_at=_iso(_value(material, "created_at")),
        updated_at=_iso(_value(material, "updated_at")),
    )


def build_material_quality_summary(material: Any) -> MaterialQualitySummary:
    issues = tuple(_quality_issue_ref(issue) for issue in _iter_relation(material, "quality_issues"))
    open_issues = tuple(issue for issue in issues if str(issue.get("status") or "").upper() not in {"CLOSED", "RESOLVED"})
    critical_issues = tuple(issue for issue in open_issues if str(issue.get("severity") or "").upper() in {"CRITICAL", "HIGH"})
    warning_issues = tuple(issue for issue in open_issues if str(issue.get("severity") or "").upper() in {"MEDIUM", "WARNING"})
    warnings: list[str] = []
    if critical_issues:
        warnings.append("Material has critical quality issues.")
    if not issues:
        warnings.append("No quality issue records are linked.")
    status = "needs_review" if open_issues else "good"
    return MaterialQualitySummary(
        status=status,
        open_issues=len(open_issues),
        critical_issues=len(critical_issues),
        warning_issues=len(warning_issues),
        issues=issues,
        warnings=tuple(warnings),
    )


def build_material_evidence_summary(
    material: Any,
    *,
    moderation_preview_refs: Iterable[Mapping[str, Any]] | None = None,
) -> MaterialEvidenceSummary:
    documents = tuple(_document_ref(document) for document in _iter_relation(material, "documents"))
    source_refs = tuple(_catalog_product_ref(product) for product in _iter_relation(material, "catalog_products"))
    moderation_refs = tuple(dict(ref) for ref in moderation_preview_refs or ())
    warnings: list[str] = []
    if not documents:
        warnings.append("No document evidence is linked.")
    if not source_refs and not moderation_refs:
        warnings.append("No source provenance is linked.")
    return MaterialEvidenceSummary(
        document_count=len(documents),
        source_ref_count=len(source_refs) + len(moderation_refs),
        documents=documents,
        source_refs=source_refs,
        moderation_preview_refs=moderation_refs,
        warnings=tuple(warnings),
    )


def build_material_characteristics_view(material: Any) -> tuple[MaterialCharacteristicView, ...]:
    values: list[MaterialCharacteristicView] = []
    for attribute in _sorted_relation(material, "attributes", sort_key="sort_order"):
        values.append(
            MaterialCharacteristicView(
                name=str(_value(attribute, "attribute_name") or ""),
                value=_value(attribute, "attribute_value"),
                unit=_unit_ref_value(_value(attribute, "unit")) or _string_id(_value(attribute, "unit_id")),
                source_ref=None,
                confidence=None,
                verification_status=None,
            )
        )
    for specification in _iter_relation(material, "specifications"):
        template = _value(specification, "template")
        values.append(
            MaterialCharacteristicView(
                name=str(_value(template, "name", "title", "field_name") or _value(template, "code") or "Specification"),
                value=_value(specification, "value"),
                unit=_value(specification, "unit"),
                source_ref=_source_ref(_value(specification, "source"), _value(specification, "source_id")),
                confidence=_decimal_or_none(_value(specification, "confidence")),
                verification_status=_enum_value(_value(specification, "verified_status")),
            )
        )
    return tuple(value for value in values if value.name or value.value not in (None, ""))


def validate_canonical_material_update(payload: Mapping[str, Any]) -> MaterialCanonicalUpdateValidation:
    errors: list[str] = []
    warnings: list[str] = []
    sanitized: dict[str, Any] = {}
    blocked_fields: list[str] = []
    for field, value in payload.items():
        if field in BLOCKED_UPDATE_FIELDS:
            blocked_fields.append(field)
            continue
        if field not in CANONICAL_UPDATE_FIELDS:
            warnings.append(f"Unsupported field ignored: {field}")
            continue
        sanitized[field] = value
    if "canonical_name" in sanitized and not str(sanitized["canonical_name"]).strip():
        errors.append("canonical_name cannot be empty.")
    if not sanitized:
        errors.append("No canonical-compatible fields were provided.")
    if blocked_fields:
        warnings.append("Raw/source/relationship fields are blocked from canonical update payload.")
    return MaterialCanonicalUpdateValidation(
        is_valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        sanitized_payload=sanitized,
        allowed_fields=tuple(sorted(CANONICAL_UPDATE_FIELDS)),
        blocked_fields=tuple(blocked_fields),
    )


def build_canonical_material_update_plan(
    material: Any,
    payload: Mapping[str, Any],
) -> MaterialCanonicalUpdatePlan:
    validation = validate_canonical_material_update(payload)
    if not validation.is_valid:
        raise ValueError("; ".join(validation.errors))
    operations = tuple(
        f"Set {field} from {_human_value(_value(material, field))} to {_human_value(value)}."
        for field, value in validation.sanitized_payload.items()
    )
    warnings = tuple(
        list(validation.warnings)
        + [
            "This is a manual canonical material update preview.",
            "No moderation decision is auto-applied.",
            "Raw/source evidence remains preview-only and is not promoted to canonical data.",
        ]
    )
    return MaterialCanonicalUpdatePlan(
        material_id=_string_id(_value(material, "id")),
        human_readable_summary=f"Prepare manual update for {_value(material, 'canonical_name') or 'material'}.",
        sanitized_payload=validation.sanitized_payload,
        operations_preview=operations,
        warnings=warnings,
        requires_manual_save=True,
        no_side_effects=True,
        source_preview_only=True,
    )


def _matches_filters(view: MaterialCanonicalView, filters: Mapping[str, Any]) -> bool:
    search = str(filters.get("search") or "").strip().lower()
    if search and search not in view.canonical_name.lower():
        return False
    status = filters.get("status")
    if status and str(view.status or "").lower() != str(status).lower():
        return False
    category_id = filters.get("category_id")
    if category_id and str((view.category or {}).get("id")) != str(category_id):
        return False
    if filters.get("has_documents") is True and view.evidence.document_count == 0:
        return False
    if filters.get("has_quality_issues") is True and view.quality.open_issues == 0:
        return False
    return True


def _view_warnings(
    material: Any,
    characteristics: tuple[MaterialCharacteristicView, ...],
    evidence: MaterialEvidenceSummary,
    quality: MaterialQualitySummary,
) -> tuple[str, ...]:
    warnings: list[str] = []
    if not _value(material, "canonical_name"):
        warnings.append("Canonical name is missing.")
    if not _value(material, "category") and not _value(material, "category_id"):
        warnings.append("Category is missing.")
    if not characteristics:
        warnings.append("No characteristics are linked.")
    warnings.extend(evidence.warnings)
    warnings.extend(quality.warnings)
    return tuple(warnings)


def _technical_profile_hints(
    material: Any,
    characteristics: tuple[MaterialCharacteristicView, ...],
) -> Mapping[str, Any]:
    names = {item.name for item in characteristics}
    return {
        "hasCharacteristics": bool(characteristics),
        "hasDimensions": bool(names & {"length_mm", "width_mm", "height_mm", "thickness_mm", "diameter_mm"}),
        "baseUnit": _unit_ref(_value(material, "base_unit"), _value(material, "base_unit_id")),
        "module2Calculations": "not_performed_by_module1",
    }


def _moderation_status(material: Any, quality: MaterialQualitySummary) -> str:
    status = str(_enum_value(_value(material, "status")) or "").lower()
    if quality.open_issues:
        return "needs_review"
    if status in {"active", "verified"}:
        return "approved"
    if status:
        return status
    return "unknown"


def _supplier_price_refs(material: Any) -> tuple[Mapping[str, Any], ...]:
    refs: list[Mapping[str, Any]] = []
    for price in _iter_relation(material, "supplier_prices"):
        supplier = _value(price, "supplier")
        refs.append(
            {
                "priceId": _string_id(_value(price, "id")),
                "supplierId": _string_id(_value(price, "supplier_id") or _value(supplier, "id")),
                "supplierName": _value(supplier, "name", "display_name"),
                "price": _decimal_to_string(_value(price, "price")),
                "currency": _value(price, "currency"),
                "unit": _value(price, "unit"),
                "region": _value(price, "region"),
                "availability": _value(price, "availability"),
                "validUntil": _iso(_value(price, "valid_until")),
            }
        )
    return tuple(refs)


def _document_ref(document: Any) -> Mapping[str, Any]:
    return {
        "documentId": _string_id(_value(document, "id")),
        "title": _value(document, "title"),
        "documentType": _enum_value(_value(document, "document_type")),
        "status": _enum_value(_value(document, "status")),
        "fileUrl": _value(document, "file_url"),
        "sourceUrl": _value(document, "source_url"),
        "issueDate": _iso(_value(document, "issue_date")),
        "expiryDate": _iso(_value(document, "expiry_date")),
    }


def _catalog_product_ref(product: Any) -> Mapping[str, Any]:
    source = _value(product, "source")
    return {
        "catalogProductId": _string_id(_value(product, "id")),
        "sourceId": _string_id(_value(product, "source_id") or _value(source, "id")),
        "sourceName": _value(source, "name", "display_name"),
        "externalUrl": _value(product, "external_url"),
        "rawTitle": _value(product, "raw_name"),
        "normalizedTitle": _value(product, "normalized_name"),
        "matchConfidence": _decimal_to_string(_value(product, "match_confidence")),
        "status": _enum_value(_value(product, "status")),
    }


def _quality_issue_ref(issue: Any) -> Mapping[str, Any]:
    return {
        "issueId": _string_id(_value(issue, "id")),
        "type": _value(issue, "issue_type"),
        "severity": _value(issue, "severity"),
        "reason": _value(issue, "reason"),
        "status": _value(issue, "status"),
        "createdAt": _iso(_value(issue, "created_at")),
    }


def _category_ref(category: Any, fallback_id: Any = None) -> Mapping[str, Any] | None:
    if category is None and fallback_id is None:
        return None
    return {
        "id": _string_id(_value(category, "id") or fallback_id),
        "name": _value(category, "name"),
        "slug": _value(category, "slug"),
        "status": _value(category, "status"),
    }


def _material_type_ref(material_type: Any, fallback_id: Any = None) -> Mapping[str, Any] | None:
    if material_type is None and fallback_id is None:
        return None
    return {
        "id": _string_id(_value(material_type, "id") or fallback_id),
        "name": _value(material_type, "name"),
        "code": _value(material_type, "code", "slug"),
    }


def _unit_ref(unit: Any, fallback_id: Any = None) -> Mapping[str, Any] | None:
    if unit is None and fallback_id is None:
        return None
    return {
        "id": _string_id(_value(unit, "id") or fallback_id),
        "name": _value(unit, "name"),
        "abbreviation": _value(unit, "abbreviation"),
        "unitType": _enum_value(_value(unit, "unit_type")),
    }


def _unit_ref_value(unit: Any) -> str | None:
    return _value(unit, "abbreviation") or _value(unit, "name")


def _source_ref(source: Any, fallback_id: Any = None) -> Mapping[str, Any] | None:
    if source is None and fallback_id is None:
        return None
    return {
        "sourceId": _string_id(_value(source, "id") or fallback_id),
        "sourceName": _value(source, "name", "display_name"),
        "sourceUrl": _value(source, "url"),
    }


def _sorted_relation(owner: Any, name: str, *, sort_key: str) -> tuple[Any, ...]:
    return tuple(sorted(_iter_relation(owner, name), key=lambda item: _value(item, sort_key) or 0))


def _iter_relation(owner: Any, name: str) -> tuple[Any, ...]:
    value = _value(owner, name)
    if value is None:
        return ()
    if isinstance(value, tuple):
        return value
    if isinstance(value, list):
        return tuple(value)
    return tuple(value) if not isinstance(value, (str, bytes, Mapping)) else ()


def _value(obj: Any, *names: str) -> Any:
    for name in names:
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if not isinstance(obj, Mapping) and hasattr(obj, name):
            return getattr(obj, name)
    return None


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    enum_value = getattr(value, "value", value)
    return str(enum_value)


def _string_id(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _iso(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return str(value) if value not in (None, "") else None


def _decimal_or_none(value: Any) -> Decimal | None:
    if isinstance(value, Decimal):
        return value
    try:
        if value in (None, ""):
            return None
        return Decimal(str(value))
    except Exception:
        return None


def _decimal_to_string(value: Any) -> str | None:
    decimal = _decimal_or_none(value)
    return str(decimal) if decimal is not None else None


def _human_value(value: Any) -> str:
    if value in (None, ""):
        return "empty"
    return str(getattr(value, "value", value))
