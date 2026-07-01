from __future__ import annotations

from datetime import datetime, timezone
from pathlib import PurePosixPath
from urllib.parse import urljoin, urlparse

from app.models.enums import DocumentType
from app.schemas.material_hub_contracts import (
    DocumentFileType,
    DocumentOrigin,
    DocumentParseStatus,
    SourceDocumentRef,
    TextExtractionSuitability,
)


DOCUMENT_EXTENSIONS = {
    ".pdf": DocumentFileType.PDF,
    ".csv": DocumentFileType.CSV,
    ".xlsx": DocumentFileType.XLSX,
    ".xls": DocumentFileType.XLSX,
    ".jpg": DocumentFileType.JPG,
    ".jpeg": DocumentFileType.JPEG,
    ".png": DocumentFileType.PNG,
    ".doc": DocumentFileType.DOC,
    ".docx": DocumentFileType.DOCX,
    ".html": DocumentFileType.HTML,
    ".htm": DocumentFileType.HTML,
    ".dwg": DocumentFileType.OTHER,
    ".rvt": DocumentFileType.OTHER,
    ".ifc": DocumentFileType.OTHER,
    ".zip": DocumentFileType.OTHER,
    ".rar": DocumentFileType.OTHER,
}

DOCUMENT_MARKERS = {
    DocumentType.CERTIFICATE.value: ("сертифик", "certificate", "sertificat", "certificat"),
    DocumentType.DECLARATION.value: ("декларац", "declaration", "declara"),
    DocumentType.TECH_CARD.value: ("техлист", "техничес", "tech", "tds", "datasheet", "карта"),
    DocumentType.INSTALLATION_GUIDE.value: ("инструкц", "монтаж", "manual", "guide"),
    DocumentType.QUALITY_PASSPORT.value: ("паспорт", "quality", "качества"),
    DocumentType.TYPICAL_NODE.value: ("узел", "node", "dwg", "rvt", "ifc"),
    DocumentType.ALBUM_OF_SOLUTIONS.value: ("альбом", "catalog", "каталог", "solutions"),
}

HTML_DOCUMENT_MARKERS = (
    "certificate",
    "certificat",
    "sertificat",
    "declaration",
    "passport",
    "manual",
    "instruction",
    "guide",
    "catalog",
    "sertifik",
    "сертифик",
    "декларац",
    "паспорт",
    "инструкц",
    "каталог",
    "техничес",
)

HTML_NON_DOCUMENT_MARKERS = (
    "/catalog/",
    "/product/",
    "/products/",
    "/category/",
    "/categories/",
    "/shop/",
    "/cart/",
)


def source_documents_from_parameters(
    parameters: dict | None,
    *,
    source_code: str | None = None,
    source_url: str | None = None,
) -> list[SourceDocumentRef]:
    payload = parameters or {}
    refs = []
    for raw in _iter_document_inputs(payload):
        ref = build_source_document_ref(raw, source_code=source_code, source_url=source_url)
        if ref:
            refs.append(ref)
    return dedupe_source_document_refs(refs)


def build_source_document_ref(
    raw: str | dict,
    *,
    source_code: str | None = None,
    source_url: str | None = None,
) -> SourceDocumentRef | None:
    data = {"url": raw} if isinstance(raw, str) else dict(raw)
    url = data.get("url") or data.get("file_url") or data.get("fileUrl") or data.get("href")
    if not url:
        return None
    absolute_url = urljoin(source_url or "", str(url))
    if not is_document_url(absolute_url, title=data.get("title")):
        return None

    title = str(data.get("title") or _filename_from_url(absolute_url) or absolute_url)
    file_type = infer_file_type(absolute_url)
    document_type = data.get("document_type") or data.get("documentType") or infer_document_type(title, absolute_url)
    extraction_suitability = infer_extraction_suitability(file_type, data.get("origin"))
    parse_status = data.get("parse_status") or data.get("parseStatus") or DocumentParseStatus.NOT_PROCESSED
    fetched_at = data.get("fetched_at") or data.get("fetchedAt") or datetime.now(timezone.utc)

    return SourceDocumentRef(
        title=title,
        url=absolute_url,
        document_type=document_type,
        file_type=file_type,
        mime_type=data.get("mime_type") or data.get("mimeType") or infer_mime_type(file_type),
        origin=data.get("origin") or DocumentOrigin.EXTERNAL_LINK,
        extraction_suitability=data.get("extraction_suitability")
        or data.get("extractionSuitability")
        or extraction_suitability,
        parse_status=parse_status,
        manufacturer=data.get("manufacturer"),
        supplier=data.get("supplier"),
        product_name=data.get("product_name") or data.get("productName"),
        source_code=data.get("source_code") or data.get("sourceCode") or source_code,
        source_url=data.get("source_url") or data.get("sourceUrl") or source_url,
        linked_catalog_product_id=data.get("linked_catalog_product_id") or data.get("linkedCatalogProductId"),
        linked_material_id=data.get("linked_material_id") or data.get("linkedMaterialId"),
        applicable_category_ids=data.get("applicable_category_ids") or data.get("applicableCategoryIds") or [],
        valid_from=data.get("valid_from") or data.get("validFrom"),
        valid_to=data.get("valid_to") or data.get("validTo"),
        fetched_at=fetched_at,
        checksum=data.get("checksum") or data.get("hash"),
        needs_review=data.get("needs_review", data.get("needsReview", True)),
        review_reason=data.get("review_reason")
        or data.get("reviewReason")
        or "Document candidate requires moderation/deduplication before canonical use.",
        dedupe_key=document_dedupe_key(title, absolute_url, document_type),
        metadata=data.get("metadata") or {},
    )


def source_documents_from_links(
    links: list[tuple[str, str]],
    *,
    page_url: str,
    source_code: str | None = None,
    document_type: str | DocumentType | None = None,
) -> list[SourceDocumentRef]:
    refs: list[SourceDocumentRef] = []
    for title, href in links:
        ref = build_source_document_ref(
            {
                "title": title,
                "url": urljoin(page_url, href),
                "document_type": getattr(document_type, "value", document_type) if document_type else None,
                "source_url": page_url,
                "source_code": source_code,
            },
            source_code=source_code,
            source_url=page_url,
        )
        if ref:
            refs.append(ref)
    return dedupe_source_document_refs(refs)


def dedupe_source_document_refs(refs: list[SourceDocumentRef]) -> list[SourceDocumentRef]:
    seen: set[str] = set()
    result: list[SourceDocumentRef] = []
    for ref in refs:
        key = ref.dedupe_key or document_dedupe_key(ref.title, ref.url, ref.document_type)
        if key in seen:
            continue
        seen.add(key)
        result.append(ref)
    return result


def is_document_url(url: str, *, title: str | None = None) -> bool:
    parsed = urlparse(url)
    path = parsed.path.lower()
    ext = PurePosixPath(path).suffix.lower()
    if ext in DOCUMENT_EXTENSIONS and ext not in {".html", ".htm"}:
        return True
    text = f"{path} {title or ''}".lower()
    if ext in {".html", ".htm"} or not ext:
        if any(marker in text for marker in HTML_NON_DOCUMENT_MARKERS):
            return False
        return any(marker in text for marker in HTML_DOCUMENT_MARKERS)
    return False


def infer_file_type(url: str) -> DocumentFileType:
    ext = PurePosixPath(urlparse(url).path.lower()).suffix
    return DOCUMENT_EXTENSIONS.get(ext, DocumentFileType.OTHER)


def infer_document_type(title: str | None, url: str | None = None) -> str:
    text = f"{title or ''} {url or ''}".lower()
    for document_type, markers in DOCUMENT_MARKERS.items():
        if any(marker in text for marker in markers):
            return document_type
    return DocumentType.TECH_CARD.value


def infer_mime_type(file_type: DocumentFileType | str) -> str | None:
    value = getattr(file_type, "value", str(file_type))
    return {
        "PDF": "application/pdf",
        "CSV": "text/csv",
        "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "JPG": "image/jpeg",
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "DOC": "application/msword",
        "DOCX": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "HTML": "text/html",
    }.get(value)


def infer_extraction_suitability(
    file_type: DocumentFileType | str,
    origin: str | DocumentOrigin | None = None,
) -> TextExtractionSuitability:
    value = getattr(file_type, "value", str(file_type))
    origin_value = getattr(origin, "value", str(origin or ""))
    if value in {"PDF", "HTML", "CSV", "XLSX", "DOC", "DOCX"}:
        return TextExtractionSuitability.TEXT_READY
    if value in {"JPG", "JPEG", "PNG"} or origin_value in {"scan", "photo"}:
        return TextExtractionSuitability.OCR_REQUIRED
    return TextExtractionSuitability.UNKNOWN


def document_dedupe_key(title: str | None, url: str | None, document_type: str | DocumentType | object) -> str:
    parsed = urlparse(url or "")
    filename = _filename_from_url(url or "")
    title_key = " ".join((title or "").lower().split())
    type_key = getattr(document_type, "value", str(document_type or ""))
    return "|".join([parsed.netloc.lower(), filename.lower(), title_key, type_key.lower()])


def _iter_document_inputs(payload: dict) -> list[str | dict]:
    values: list[str | dict] = []
    for key in ("document_refs", "documentRefs", "document_links", "documentLinks", "document_urls", "documentUrls"):
        raw = payload.get(key)
        if not raw:
            continue
        if isinstance(raw, (list, tuple, set)):
            values.extend(raw)
        else:
            values.append(raw)
    snapshot = payload.get("source_profile_snapshot") or {}
    extraction_profile = snapshot.get("extraction_profile") or {}
    parsing_rules = extraction_profile.get("parsing_rules") or {}
    file_link_rules = parsing_rules.get("file_link_rules") or {}
    for key in ("seed_document_urls", "document_urls", "documentUrls"):
        raw = file_link_rules.get(key)
        if isinstance(raw, list):
            values.extend(raw)
    return values


def _filename_from_url(url: str) -> str:
    path = urlparse(url).path
    return PurePosixPath(path).name


__all__ = [
    "DOCUMENT_EXTENSIONS",
    "source_documents_from_parameters",
    "build_source_document_ref",
    "source_documents_from_links",
    "dedupe_source_document_refs",
    "is_document_url",
    "infer_file_type",
    "infer_document_type",
    "infer_mime_type",
    "infer_extraction_suitability",
    "document_dedupe_key",
]
