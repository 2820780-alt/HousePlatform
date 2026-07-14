from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_canonical_material_store import MaterialCanonicalView
from app.services.module1_extraction_blueprint_registry import ExtractionBlueprintRegistry
from app.services.source_document_refs import is_document_url


DOCUMENT_TYPES = frozenset(
    {
        "certificate",
        "declaration",
        "technical_sheet",
        "installation_instruction",
        "passport",
        "album_solution",
        "node_detail",
        "manual",
        "warranty",
        "other",
    }
)

DOCUMENT_TYPE_ALIASES: Mapping[str, str] = {
    "album_of_solutions": "album_solution",
    "album_solution": "album_solution",
    "certificate": "certificate",
    "declaration": "declaration",
    "fire_certificate": "certificate",
    "installation_guide": "installation_instruction",
    "installation_instruction": "installation_instruction",
    "manual": "manual",
    "mill_certificate": "certificate",
    "node_detail": "node_detail",
    "passport": "passport",
    "quality_passport": "passport",
    "safety_sheet": "technical_sheet",
    "sanitary_certificate": "certificate",
    "technical_sheet": "technical_sheet",
    "technical_approval": "technical_sheet",
    "tech_card": "technical_sheet",
    "test_report": "certificate",
    "typical_node": "node_detail",
    "warranty": "warranty",
    "coating_warranty": "warranty",
}

DOCUMENT_MARKERS: Mapping[str, tuple[str, ...]] = {
    "certificate": ("certificate", "certificat", "sertificat", "сертифик", "fire_certificate", "test_report"),
    "declaration": ("declaration", "declara", "деклара"),
    "technical_sheet": ("technical", "tech", "datasheet", "tds", "техничес", "tech_card", "safety_sheet"),
    "installation_instruction": ("installation", "instruction", "guide", "монтаж", "инструкц"),
    "passport": ("passport", "паспорт", "quality"),
    "album_solution": ("album", "solution", "catalog", "альбом", "решени"),
    "node_detail": ("node", "detail", "dwg", "rvt", "ifc", "узел"),
    "manual": ("manual", "guide", "руковод"),
    "warranty": ("warranty", "гарант"),
}


@dataclass(frozen=True)
class MaterialDocumentLink:
    url: str
    link_type: str
    title: str | None
    is_document: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MaterialDocumentRecord:
    document_id: str | None
    title: str
    document_type: str
    material_id: str | None
    material_group: str | None
    manufacturer: str | None
    supplier: str | None
    source_url: str | None
    file_url: str | None
    storage_ref: str | None
    issue_date: str | None
    expiry_date: str | None
    status: str
    confidence: Decimal | None
    evidence_refs: tuple[Mapping[str, Any], ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class MaterialDocumentEvidence:
    confirms: tuple[str, ...]
    material_id: str | None
    material_group: str | None
    source: str | None
    document: MaterialDocumentRecord | None
    raw_link: MaterialDocumentLink | None
    confidence: Decimal | None
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class DocumentValidationReport:
    is_valid: bool
    document_id: str | None
    document_type: str
    status: str
    missing_fields: tuple[str, ...]
    warnings: tuple[str, ...]
    expired: bool
    linked_to_material: bool
    message: str


@dataclass(frozen=True)
class DocumentReadinessReport:
    material_id: str | None
    material_name: str | None
    material_group: str | None
    documents_present: tuple[str, ...]
    required_document_hints: tuple[str, ...]
    missing_document_hints: tuple[str, ...]
    expired_documents: tuple[str, ...]
    unlinked_documents: tuple[str, ...]
    raw_links_pending: tuple[MaterialDocumentLink, ...]
    warnings: tuple[str, ...]
    status: str
    message: str


@dataclass(frozen=True)
class DocumentPackage:
    material_id: str | None
    material_name: str
    material_group: str | None
    documents: tuple[MaterialDocumentRecord, ...]
    evidence: tuple[MaterialDocumentEvidence, ...]
    source_refs: tuple[Mapping[str, Any], ...]
    required_document_hints: tuple[str, ...]
    missing_document_hints: tuple[str, ...]
    readiness: DocumentReadinessReport
    warnings: tuple[str, ...]


def build_document_record_from_material_document(document: Any, *, material_group: str | None = None) -> MaterialDocumentRecord:
    title = _as_string(_value(document, "title")) or "Untitled document"
    file_url = _as_string(_value(document, "file_url", "fileUrl"))
    source_url = _as_string(_value(document, "source_url", "sourceUrl"))
    document_type = classify_document_type(
        title,
        url=file_url or source_url,
        metadata={"document_type": _value(document, "document_type", "documentType")},
    )
    record = MaterialDocumentRecord(
        document_id=_as_string(_value(document, "id", "documentId")),
        title=title,
        document_type=document_type,
        material_id=_as_string(_value(document, "material_id", "materialId")),
        material_group=material_group,
        manufacturer=_name_or_id(_value(document, "manufacturer")) or _as_string(_value(document, "manufacturer_id", "manufacturerId")),
        supplier=_name_or_id(_value(document, "supplier")) or _as_string(_value(document, "supplier_id", "supplierId")),
        source_url=source_url,
        file_url=file_url,
        storage_ref=_as_string(_value(document, "storage_ref", "storageRef")),
        issue_date=_date_string(_value(document, "issue_date", "issueDate")),
        expiry_date=_date_string(_value(document, "expiry_date", "expiryDate")),
        status=normalize_document_status(document),
        confidence=_decimal(_value(document, "confidence")),
        evidence_refs=_evidence_refs(document),
        warnings=tuple(),
    )
    report = validate_document_record(record)
    return MaterialDocumentRecord(
        **{**record.__dict__, "warnings": report.warnings}
    )


def build_document_evidence_from_raw_link(
    raw_link: Mapping[str, Any] | Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
) -> MaterialDocumentEvidence:
    title = _as_string(_value(raw_link, "title")) or _as_string(_value(raw_link, "name"))
    url = _as_string(_value(raw_link, "url", "file_url", "fileUrl", "href"))
    link = _document_link(url, title)
    warnings = list(link.warnings)
    document = None
    if link.is_document:
        document = MaterialDocumentRecord(
            document_id=_as_string(_value(raw_link, "document_id", "documentId")),
            title=title or url or "Raw document link",
            document_type=classify_document_type(title, url=url, metadata=raw_link if isinstance(raw_link, Mapping) else None),
            material_id=material_id or _as_string(_value(raw_link, "linked_material_id", "linkedMaterialId")),
            material_group=material_group,
            manufacturer=_as_string(_value(raw_link, "manufacturer")),
            supplier=_as_string(_value(raw_link, "supplier")),
            source_url=_as_string(_value(raw_link, "source_url", "sourceUrl")),
            file_url=url,
            storage_ref=None,
            issue_date=_date_string(_value(raw_link, "valid_from", "validFrom", "issue_date", "issueDate")),
            expiry_date=_date_string(_value(raw_link, "valid_to", "validTo", "expiry_date", "expiryDate")),
            status=normalize_document_status(raw_link),
            confidence=_decimal(_value(raw_link, "confidence")),
            evidence_refs=(MappingProxyType({"source": "raw_document_link", "url": url}),),
            warnings=tuple(),
        )
        validation = validate_document_record(document)
        document = MaterialDocumentRecord(**{**document.__dict__, "warnings": validation.warnings})
        warnings.extend(validation.warnings)
    return MaterialDocumentEvidence(
        confirms=_confirms_for_type(document.document_type if document else None),
        material_id=material_id or (document.material_id if document else None),
        material_group=material_group,
        source=_as_string(_value(raw_link, "source_code", "sourceCode", "source")),
        document=document,
        raw_link=link,
        confidence=_decimal(_value(raw_link, "confidence")),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def list_documents_for_material(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialDocumentRecord, ...]:
    group_code = _group_code(canonical_material_view)
    records = [
        build_document_record_from_material_document(
            {**dict(item), "materialId": canonical_material_view.material_id},
            material_group=group_code,
        )
        for item in canonical_material_view.evidence.documents
    ]
    return tuple(records)


def build_document_package(canonical_material_view: MaterialCanonicalView) -> DocumentPackage:
    documents = list_documents_for_material(canonical_material_view)
    evidence = tuple(
        MaterialDocumentEvidence(
            confirms=_confirms_for_type(document.document_type),
            material_id=document.material_id or canonical_material_view.material_id,
            material_group=document.material_group,
            source=document.source_url,
            document=document,
            raw_link=None,
            confidence=document.confidence,
            warnings=document.warnings,
        )
        for document in documents
    )
    readiness = build_document_readiness_report(canonical_material_view)
    warnings = tuple(
        dict.fromkeys(
            tuple(warning for document in documents for warning in document.warnings)
            + canonical_material_view.evidence.warnings
            + readiness.warnings
        )
    )
    return DocumentPackage(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        material_group=_group_code(canonical_material_view),
        documents=documents,
        evidence=evidence,
        source_refs=canonical_material_view.evidence.source_refs,
        required_document_hints=readiness.required_document_hints,
        missing_document_hints=readiness.missing_document_hints,
        readiness=readiness,
        warnings=warnings,
    )


def classify_document_type(
    raw_title: str | None,
    url: str | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> str:
    metadata = metadata or {}
    explicit_raw = metadata.get("document_type") or metadata.get("documentType") or metadata.get("type")
    explicit = _normalize_document_type(_enum_value(explicit_raw))
    if explicit:
        return explicit
    text = f"{raw_title or ''} {url or ''}".lower()
    for document_type, markers in DOCUMENT_MARKERS.items():
        if any(marker in text for marker in markers):
            return document_type
    return "other"


def validate_document_record(document: MaterialDocumentRecord) -> DocumentValidationReport:
    missing = []
    warnings = list(document.warnings)
    if not document.title:
        missing.append("title")
    if document.document_type not in DOCUMENT_TYPES:
        missing.append("document_type")
    if not document.file_url and not document.source_url and not document.storage_ref:
        missing.append("file_or_source_url")
    url = document.file_url or document.source_url
    if url and not is_document_url(url, title=document.title):
        warnings.append("URL points to a site/card page, not a document record.")
    linked = bool(document.material_id or document.material_group)
    if not linked:
        warnings.append("Document is not linked to a material or material group.")
    expired = _is_expired(document.expiry_date) or document.status == "expired"
    if expired:
        warnings.append("Document is expired.")
    is_valid = not missing and (not url or is_document_url(url, title=document.title))
    return DocumentValidationReport(
        is_valid=is_valid,
        document_id=document.document_id,
        document_type=document.document_type,
        status=document.status,
        missing_fields=tuple(missing),
        warnings=tuple(dict.fromkeys(warnings)),
        expired=expired,
        linked_to_material=linked,
        message="Document record is valid read-only evidence." if is_valid else "Document record needs review.",
    )


def build_document_readiness_report(canonical_material_view: MaterialCanonicalView) -> DocumentReadinessReport:
    group_code = _group_code(canonical_material_view)
    documents = list_documents_for_material(canonical_material_view)
    present = tuple(dict.fromkeys(document.document_type for document in documents))
    required = get_required_document_hints(group_code)
    missing = get_missing_document_hints(canonical_material_view)
    validations = tuple(validate_document_record(document) for document in documents)
    expired = tuple(document.document_id or document.title for document, report in zip(documents, validations) if report.expired)
    unlinked = tuple(document.document_id or document.title for document, report in zip(documents, validations) if not report.linked_to_material)
    raw_links = _raw_links_pending(canonical_material_view)
    warnings = list(canonical_material_view.evidence.warnings)
    warnings.extend(warning for report in validations for warning in report.warnings)
    if raw_links:
        warnings.append("Raw document links are evidence candidates and are not MaterialDocument records yet.")
    if missing:
        status = "missing_documents"
    elif expired:
        status = "expired_documents"
    else:
        status = "ready"
    return DocumentReadinessReport(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        material_group=group_code,
        documents_present=present,
        required_document_hints=required,
        missing_document_hints=missing,
        expired_documents=expired,
        unlinked_documents=unlinked,
        raw_links_pending=raw_links,
        warnings=tuple(dict.fromkeys(warnings)),
        status=status,
        message="Document readiness evaluated without OCR, download or parsing.",
    )


def get_required_document_hints(group_code: str | None) -> tuple[str, ...]:
    if not group_code:
        return tuple()
    hints = ExtractionBlueprintRegistry().get_document_hints(group_code)
    return tuple(dict.fromkeys(_normalize_document_type(hint) or "other" for hint in hints))


def get_missing_document_hints(canonical_material_view: MaterialCanonicalView) -> tuple[str, ...]:
    required = get_required_document_hints(_group_code(canonical_material_view))
    present = {document.document_type for document in list_documents_for_material(canonical_material_view)}
    return tuple(hint for hint in required if hint not in present)


def normalize_document_status(document: Any) -> str:
    status = _enum_value(_value(document, "status", "documentStatus")) or "needs_review"
    normalized = status.lower()
    if normalized in {"active", "verified", "valid"}:
        return "active"
    if normalized in {"expired"}:
        return "expired"
    if normalized in {"archived"}:
        return "archived"
    if normalized in {"rejected"}:
        return "rejected"
    return "needs_review"


def _document_link(url: str | None, title: str | None) -> MaterialDocumentLink:
    if not url:
        return MaterialDocumentLink(url="", link_type="missing", title=title, is_document=False, warnings=("Document URL is missing.",))
    is_doc = is_document_url(url, title=title)
    warnings = tuple() if is_doc else ("URL is a source/card reference, not a document.",)
    return MaterialDocumentLink(
        url=url,
        link_type="document" if is_doc else "source_reference",
        title=title,
        is_document=is_doc,
        warnings=warnings,
    )


def _raw_links_pending(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialDocumentLink, ...]:
    links: list[MaterialDocumentLink] = []
    for ref in canonical_material_view.evidence.source_refs + canonical_material_view.evidence.moderation_preview_refs:
        for key in ("documentUrl", "document_url", "fileUrl", "file_url", "url"):
            url = ref.get(key)
            if url:
                link = _document_link(str(url), _as_string(ref.get("title") or ref.get("rawTitle")))
                if link.is_document:
                    links.append(link)
    return tuple(links)


def _evidence_refs(document: Any) -> tuple[Mapping[str, Any], ...]:
    refs: list[Mapping[str, Any]] = []
    source = _value(document, "source")
    if source:
        refs.append(
            MappingProxyType(
                {
                    "sourceId": _as_string(_value(source, "id")),
                    "sourceName": _as_string(_value(source, "name", "display_name")),
                    "sourceUrl": _as_string(_value(source, "url")),
                }
            )
        )
    source_url = _as_string(_value(document, "source_url", "sourceUrl"))
    if source_url:
        refs.append(MappingProxyType({"sourceUrl": source_url}))
    return tuple(refs)


def _confirms_for_type(document_type: str | None) -> tuple[str, ...]:
    return {
        "certificate": ("compliance", "quality"),
        "declaration": ("compliance",),
        "technical_sheet": ("technical_profile", "characteristics"),
        "installation_instruction": ("installation_requirements",),
        "passport": ("batch_quality", "technical_profile"),
        "album_solution": ("system_solution",),
        "node_detail": ("node_detail",),
        "manual": ("usage_instructions",),
        "warranty": ("warranty_terms",),
        "other": ("supporting_evidence",),
    }.get(document_type or "other", ("supporting_evidence",))


def _group_code(canonical_material_view: MaterialCanonicalView) -> str | None:
    group = canonical_material_view.group or {}
    category = canonical_material_view.category or {}
    return _as_string(group.get("code") or group.get("slug") or category.get("slug"))


def _normalize_document_type(value: str | None) -> str | None:
    if not value:
        return None
    normalized = str(value).strip().lower().replace("-", "_").replace(" ", "_")
    normalized = DOCUMENT_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in DOCUMENT_TYPES else None


def _is_expired(value: str | None) -> bool:
    if not value:
        return False
    parsed = _date(value)
    return bool(parsed and parsed < date.today())


def _date_string(value: Any) -> str | None:
    parsed = _date(value)
    return parsed.isoformat() if parsed else None


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        except ValueError:
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
    return None


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _name_or_id(value: Any) -> str | None:
    if value is None:
        return None
    return _as_string(_value(value, "name", "display_name", "title", "id"))


def _value(obj: Any, *names: str) -> Any:
    for name in names:
        if obj is None:
            return None
        if isinstance(obj, Mapping) and name in obj:
            return obj[name]
        if not isinstance(obj, Mapping) and hasattr(obj, name):
            return getattr(obj, name)
    return None


def _enum_value(value: Any) -> str | None:
    if value is None:
        return None
    return str(getattr(value, "value", value))


def _as_string(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)
