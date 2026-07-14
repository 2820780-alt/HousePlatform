from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Mapping

from app.services.module1_canonical_material_store import MaterialCanonicalView


PARTICIPANT_TYPES = frozenset(
    {
        "supplier",
        "manufacturer",
        "brand",
        "contractor",
        "source",
        "distributor",
        "unknown",
    }
)

PARTICIPANT_TYPE_ALIASES: Mapping[str, str] = {
    "vendor": "supplier",
    "seller": "supplier",
    "supplier_site": "supplier",
    "manufacturer_site": "manufacturer",
    "factory": "manufacturer",
    "producer": "manufacturer",
    "tm": "brand",
    "trademark": "brand",
    "contractor_company": "contractor",
    "source_profile": "source",
    "data_source": "source",
    "dealer": "distributor",
    "retailer": "distributor",
}


@dataclass(frozen=True)
class ParticipantContactInfo:
    email: str | None = None
    phone: str | None = None
    site: str | None = None
    address: str | None = None


@dataclass(frozen=True)
class ParticipantRegionCoverage:
    country: str | None = None
    region: str | None = None
    city: str | None = None
    address: str | None = None


@dataclass(frozen=True)
class ParticipantSourceLink:
    source_id: str | None
    source_code: str | None
    source_name: str | None
    source_type: str | None
    url: str | None
    reliability: str | None
    status: str | None
    provenance: Mapping[str, Any]


@dataclass(frozen=True)
class ParticipantMaterialLink:
    material_id: str | None
    material_group: str | None
    material_name: str | None
    relation: str
    price_ref_ids: tuple[str, ...] = tuple()


@dataclass(frozen=True)
class MaterialParticipantRecord:
    participant_id: str | None
    stable_key: str
    participant_type: str
    display_name: str
    legal_name: str | None
    brand_name: str | None
    manufacturer_name: str | None
    supplier_name: str | None
    contacts: ParticipantContactInfo
    regions: tuple[ParticipantRegionCoverage, ...]
    source_links: tuple[ParticipantSourceLink, ...]
    material_links: tuple[ParticipantMaterialLink, ...]
    related_price_refs: tuple[Mapping[str, Any], ...]
    confidence: Decimal
    warnings: tuple[str, ...]
    provenance_refs: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class ParticipantReadinessReport:
    material_id: str | None
    material_name: str | None
    material_group: str | None
    participant_count: int
    participant_types: tuple[str, ...]
    has_supplier: bool
    has_manufacturer: bool
    has_brand: bool
    has_region: bool
    has_source_evidence: bool
    duplicate_stable_keys: tuple[str, ...]
    unknown_participants: tuple[str, ...]
    missing_details: tuple[str, ...]
    warnings: tuple[str, ...]
    status: str
    message: str


@dataclass(frozen=True)
class ParticipantDirectoryPackage:
    material_id: str | None
    material_name: str
    material_group: str | None
    participants: tuple[MaterialParticipantRecord, ...]
    readiness: ParticipantReadinessReport
    warnings: tuple[str, ...]


def build_participant_record_from_supplier(
    supplier: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialParticipantRecord:
    display_name = normalize_participant_name(_value(supplier, "name", "display_name", "title"))
    participant_id = _as_string(_value(supplier, "id", "supplierId", "supplier_id"))
    warnings = []
    if not display_name:
        display_name = "Unknown supplier"
        warnings.append("Supplier name is missing.")
    contact = ParticipantContactInfo(
        email=_as_string(_value(supplier, "email")),
        phone=_as_string(_value(supplier, "phone")),
        site=_as_string(_value(supplier, "site", "url", "website")),
        address=_as_string(_value(supplier, "address")),
    )
    region = _region_from_value(supplier)
    source_links = tuple(
        link
        for link in (
            _source_link_from_values(
                source_id=participant_id,
                source_code=None,
                source_name=display_name,
                source_type="supplier",
                url=contact.site,
                reliability=None,
                status=_enum_value(_value(supplier, "status")),
                provenance={"source": "Supplier"},
            ),
        )
        if link is not None
    )
    material_links = _material_links(material_id, material_group, material_name, "supplier")
    return MaterialParticipantRecord(
        participant_id=participant_id,
        stable_key=_stable_key("supplier", participant_id, display_name),
        participant_type="supplier",
        display_name=display_name,
        legal_name=_as_string(_value(supplier, "legal_name", "legalName", "name")),
        brand_name=None,
        manufacturer_name=None,
        supplier_name=display_name,
        contacts=contact,
        regions=(region,) if region else tuple(),
        source_links=source_links,
        material_links=material_links,
        related_price_refs=tuple(),
        confidence=Decimal("0.90"),
        warnings=tuple(warnings),
        provenance_refs=(MappingProxyType({"source": "Supplier", "supplierId": participant_id}),),
    )


def build_participant_record_from_source(
    source: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialParticipantRecord:
    source_type = _enum_value(_value(source, "source_type", "sourceType")) or _as_string(_value(source, "linked_participant", "linkedParticipant"))
    participant_type = normalize_participant_type(_value(source, "linked_participant", "linkedParticipant") or source_type or "source")
    source_id = _as_string(_value(source, "id", "sourceId", "source_id"))
    source_code = _as_string(_value(source, "source_code", "sourceCode", "code"))
    display_name = normalize_participant_name(_value(source, "name", "display_name", "displayName", "sourceName"))
    if not display_name:
        display_name = source_code or "Unknown source"
    source_link = _source_link_from_values(
        source_id=source_id,
        source_code=source_code,
        source_name=display_name,
        source_type=source_type,
        url=_as_string(_value(source, "url", "base_url", "baseUrl", "externalUrl")),
        reliability=_as_string(_value(source, "reliability")),
        status=_enum_value(_value(source, "status")),
        provenance={"source": "Source"},
    )
    return MaterialParticipantRecord(
        participant_id=source_id or source_code,
        stable_key=_stable_key(participant_type, source_id or source_code, display_name),
        participant_type=participant_type,
        display_name=display_name,
        legal_name=None,
        brand_name=display_name if participant_type == "brand" else None,
        manufacturer_name=display_name if participant_type == "manufacturer" else None,
        supplier_name=display_name if participant_type in {"supplier", "distributor"} else None,
        contacts=ParticipantContactInfo(site=_as_string(_value(source, "url", "base_url", "baseUrl", "externalUrl"))),
        regions=tuple(region for region in (_region_from_value(source),) if region is not None),
        source_links=(source_link,) if source_link else tuple(),
        material_links=_material_links(material_id, material_group, material_name, participant_type),
        related_price_refs=tuple(),
        confidence=Decimal("0.70") if participant_type == "source" else Decimal("0.76"),
        warnings=tuple(),
        provenance_refs=(MappingProxyType({"source": "Source", "sourceId": source_id, "sourceCode": source_code}),),
    )


def build_participant_record_from_material_ref(
    material_ref: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialParticipantRecord:
    participant_type = normalize_participant_type(
        _value(material_ref, "participant_type", "participantType", "type", "relation")
        or _infer_material_ref_type(material_ref)
    )
    display_name = normalize_participant_name(
        _value(
            material_ref,
            "display_name",
            "displayName",
            "name",
            "supplierName",
            "manufacturerName",
            "manufacturer",
            "brandName",
            "brand",
        )
    )
    participant_id = _as_string(_value(material_ref, "participant_id", "participantId", "id", "supplierId", "manufacturerId", "brandId"))
    warnings = []
    if not display_name:
        display_name = "Unknown participant"
        participant_type = "unknown"
        warnings.append("Participant name is missing.")
    return MaterialParticipantRecord(
        participant_id=participant_id,
        stable_key=_stable_key(participant_type, participant_id, display_name),
        participant_type=participant_type,
        display_name=display_name,
        legal_name=_as_string(_value(material_ref, "legal_name", "legalName")),
        brand_name=display_name if participant_type == "brand" else _as_string(_value(material_ref, "brand", "brandName")),
        manufacturer_name=display_name if participant_type == "manufacturer" else _as_string(_value(material_ref, "manufacturer", "manufacturerName")),
        supplier_name=display_name if participant_type in {"supplier", "distributor"} else _as_string(_value(material_ref, "supplierName", "supplier")),
        contacts=ParticipantContactInfo(
            email=_as_string(_value(material_ref, "email")),
            phone=_as_string(_value(material_ref, "phone")),
            site=_as_string(_value(material_ref, "site", "url", "website")),
            address=_as_string(_value(material_ref, "address")),
        ),
        regions=tuple(region for region in (_region_from_value(material_ref),) if region is not None),
        source_links=tuple(),
        material_links=_material_links(
            material_id or _as_string(_value(material_ref, "material_id", "materialId")),
            material_group or _as_string(_value(material_ref, "material_group", "materialGroup")),
            material_name or _as_string(_value(material_ref, "material_name", "materialName")),
            participant_type,
        ),
        related_price_refs=tuple(),
        confidence=classify_participant_confidence({"participant_type": participant_type, "source": "material_ref"}),
        warnings=tuple(warnings),
        provenance_refs=(MappingProxyType({"source": "material_ref"}),),
    )


def build_participant_record_from_price_ref(
    price_ref: Any,
    *,
    material_id: str | None = None,
    material_group: str | None = None,
    material_name: str | None = None,
) -> MaterialParticipantRecord:
    supplier_name = normalize_participant_name(_value(price_ref, "supplierName", "supplier_name", "supplier", "name"))
    supplier_id = _as_string(_value(price_ref, "supplierId", "supplier_id", "supplier"))
    warnings = []
    if not supplier_name:
        supplier_name = "Unknown supplier"
        warnings.append("Supplier name is missing in price reference.")
    price_id = _as_string(_value(price_ref, "priceId", "price_id", "id"))
    region = _region_from_value(price_ref)
    return MaterialParticipantRecord(
        participant_id=supplier_id,
        stable_key=_stable_key("supplier", supplier_id, supplier_name),
        participant_type="supplier",
        display_name=supplier_name,
        legal_name=None,
        brand_name=None,
        manufacturer_name=None,
        supplier_name=supplier_name,
        contacts=ParticipantContactInfo(),
        regions=(region,) if region else tuple(),
        source_links=tuple(),
        material_links=_material_links(material_id, material_group, material_name, "supplier", price_ref_ids=(price_id,) if price_id else tuple()),
        related_price_refs=(MappingProxyType(dict(price_ref)),) if isinstance(price_ref, Mapping) else (MappingProxyType({"priceId": price_id}),),
        confidence=Decimal("0.80") if supplier_id or supplier_name != "Unknown supplier" else Decimal("0.45"),
        warnings=tuple(warnings),
        provenance_refs=(MappingProxyType({"source": "supplier_price_ref", "priceId": price_id}),),
    )


def normalize_participant_type(value: Any) -> str:
    normalized = _normalize_key(_enum_value(value))
    if not normalized:
        return "unknown"
    normalized = PARTICIPANT_TYPE_ALIASES.get(normalized, normalized)
    return normalized if normalized in PARTICIPANT_TYPES else "unknown"


def normalize_participant_name(value: Any) -> str | None:
    text = _as_string(value)
    if not text:
        return None
    return " ".join(text.strip().split()) or None


def list_participants_for_material(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialParticipantRecord, ...]:
    return deduplicate_participant_records(_collect_participants(canonical_material_view))


def build_participant_directory_package(canonical_material_view: MaterialCanonicalView) -> ParticipantDirectoryPackage:
    participants = list_participants_for_material(canonical_material_view)
    readiness = build_participant_readiness_report(canonical_material_view)
    warnings = tuple(
        dict.fromkeys(
            tuple(warning for participant in participants for warning in participant.warnings)
            + readiness.warnings
        )
    )
    return ParticipantDirectoryPackage(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        material_group=_group_code(canonical_material_view),
        participants=participants,
        readiness=readiness,
        warnings=warnings,
    )


def build_participant_readiness_report(canonical_material_view: MaterialCanonicalView) -> ParticipantReadinessReport:
    raw_participants = _collect_participants(canonical_material_view)
    participants = deduplicate_participant_records(raw_participants)
    participant_types = tuple(sorted({participant.participant_type for participant in participants}))
    duplicate_keys = _duplicate_keys(raw_participants)
    unknown = tuple(participant.display_name for participant in participants if participant.participant_type == "unknown")
    has_supplier = any(participant.participant_type in {"supplier", "distributor"} for participant in participants)
    has_manufacturer = any(participant.participant_type == "manufacturer" for participant in participants)
    has_brand = any(participant.participant_type == "brand" for participant in participants)
    has_region = any(participant.regions for participant in participants)
    has_source = any(participant.participant_type == "source" or participant.source_links for participant in participants)
    missing = []
    if not participants:
        missing.append("participants")
    if not has_supplier:
        missing.append("supplier")
    if not has_manufacturer:
        missing.append("manufacturer")
    if not has_brand:
        missing.append("brand")
    if not has_region:
        missing.append("regional_coverage")
    if not has_source:
        missing.append("source_evidence")
    warnings = []
    if duplicate_keys:
        warnings.append("Duplicate participant records were detected and can be merged read-only.")
    if unknown:
        warnings.append("Some participant records have unknown type.")
    if missing:
        warnings.append("Participant directory has missing details.")
    status = "ready"
    if not participants:
        status = "missing_participants"
    elif duplicate_keys or unknown or missing:
        status = "needs_review"
    return ParticipantReadinessReport(
        material_id=canonical_material_view.material_id,
        material_name=canonical_material_view.canonical_name,
        material_group=_group_code(canonical_material_view),
        participant_count=len(participants),
        participant_types=participant_types,
        has_supplier=has_supplier,
        has_manufacturer=has_manufacturer,
        has_brand=has_brand,
        has_region=has_region,
        has_source_evidence=has_source,
        duplicate_stable_keys=duplicate_keys,
        unknown_participants=unknown,
        missing_details=tuple(missing),
        warnings=tuple(warnings),
        status=status,
        message="Participant directory evaluated as read-only data records.",
    )


def classify_participant_confidence(participant: Any) -> Decimal:
    explicit = _decimal(_value(participant, "confidence"))
    if explicit is not None:
        return explicit
    participant_type = normalize_participant_type(_value(participant, "participant_type", "participantType", "type"))
    source = _normalize_key(_value(participant, "source"))
    if source == "supplier":
        return Decimal("0.90")
    if source == "supplier_price_ref":
        return Decimal("0.80")
    if source == "material_ref":
        return Decimal("0.75")
    if participant_type == "source":
        return Decimal("0.70")
    if participant_type == "unknown":
        return Decimal("0.40")
    return Decimal("0.65")


def deduplicate_participant_records(participants: tuple[MaterialParticipantRecord, ...] | list[MaterialParticipantRecord]) -> tuple[MaterialParticipantRecord, ...]:
    merged: dict[str, MaterialParticipantRecord] = {}
    order: list[str] = []
    for participant in participants:
        key = participant.stable_key
        if key not in merged:
            merged[key] = participant
            order.append(key)
            continue
        existing = merged[key]
        merged[key] = _merge_participant(existing, participant)
    return tuple(merged[key] for key in order)


def build_participant_source_links(participant: MaterialParticipantRecord) -> tuple[ParticipantSourceLink, ...]:
    return participant.source_links


def _collect_participants(canonical_material_view: MaterialCanonicalView) -> tuple[MaterialParticipantRecord, ...]:
    material_id = canonical_material_view.material_id
    material_group = _group_code(canonical_material_view)
    material_name = canonical_material_view.canonical_name
    participants: list[MaterialParticipantRecord] = []
    for ref in _material_refs_from_canonical_view(canonical_material_view):
        participants.append(
            build_participant_record_from_material_ref(
                ref,
                material_id=material_id,
                material_group=material_group,
                material_name=material_name,
            )
        )
    for price_ref in canonical_material_view.supplier_price_refs:
        participants.append(
            build_participant_record_from_price_ref(
                price_ref,
                material_id=material_id,
                material_group=material_group,
                material_name=material_name,
            )
        )
    for source_ref in canonical_material_view.evidence.source_refs + canonical_material_view.evidence.moderation_preview_refs:
        participants.append(
            build_participant_record_from_source(
                {
                    "id": _value(source_ref, "sourceId"),
                    "sourceCode": _value(source_ref, "sourceCode"),
                    "sourceName": _value(source_ref, "sourceName") or _value(source_ref, "rawTitle"),
                    "sourceType": _value(source_ref, "sourceType") or "source",
                    "url": _value(source_ref, "externalUrl") or _value(source_ref, "sourceUrl") or _value(source_ref, "url"),
                    "status": _value(source_ref, "status"),
                },
                material_id=material_id,
                material_group=material_group,
                material_name=material_name,
            )
        )
    return tuple(participants)


def _material_refs_from_canonical_view(canonical_material_view: MaterialCanonicalView) -> tuple[Mapping[str, Any], ...]:
    refs: list[Mapping[str, Any]] = []
    for container in (canonical_material_view.source_provenance, canonical_material_view.technical_profile_hints):
        for participant_type, keys in (
            ("manufacturer", ("manufacturer", "manufacturerName")),
            ("brand", ("brand", "brandName")),
            ("supplier", ("supplier", "supplierName")),
        ):
            for key in keys:
                value = container.get(key) if isinstance(container, Mapping) else None
                if value:
                    refs.append(
                        MappingProxyType(
                            {
                                "participant_type": participant_type,
                                "displayName": value,
                                "source": "canonical_view",
                            }
                        )
                    )
                    break
    return tuple(refs)


def _merge_participant(left: MaterialParticipantRecord, right: MaterialParticipantRecord) -> MaterialParticipantRecord:
    warnings = tuple(dict.fromkeys(left.warnings + right.warnings + ("Duplicate participant record merged.",)))
    return MaterialParticipantRecord(
        participant_id=left.participant_id or right.participant_id,
        stable_key=left.stable_key,
        participant_type=left.participant_type if left.participant_type != "unknown" else right.participant_type,
        display_name=left.display_name if left.display_name != "Unknown participant" else right.display_name,
        legal_name=left.legal_name or right.legal_name,
        brand_name=left.brand_name or right.brand_name,
        manufacturer_name=left.manufacturer_name or right.manufacturer_name,
        supplier_name=left.supplier_name or right.supplier_name,
        contacts=_merge_contact(left.contacts, right.contacts),
        regions=_dedupe_regions(left.regions + right.regions),
        source_links=_dedupe_source_links(left.source_links + right.source_links),
        material_links=_dedupe_material_links(left.material_links + right.material_links),
        related_price_refs=_dedupe_mappings(left.related_price_refs + right.related_price_refs),
        confidence=max(left.confidence, right.confidence),
        warnings=warnings,
        provenance_refs=_dedupe_mappings(left.provenance_refs + right.provenance_refs),
    )


def _merge_contact(left: ParticipantContactInfo, right: ParticipantContactInfo) -> ParticipantContactInfo:
    return ParticipantContactInfo(
        email=left.email or right.email,
        phone=left.phone or right.phone,
        site=left.site or right.site,
        address=left.address or right.address,
    )


def _material_links(
    material_id: str | None,
    material_group: str | None,
    material_name: str | None,
    relation: str,
    *,
    price_ref_ids: tuple[str, ...] = tuple(),
) -> tuple[ParticipantMaterialLink, ...]:
    if not (material_id or material_group or material_name):
        return tuple()
    return (
        ParticipantMaterialLink(
            material_id=material_id,
            material_group=material_group,
            material_name=material_name,
            relation=relation,
            price_ref_ids=price_ref_ids,
        ),
    )


def _source_link_from_values(
    *,
    source_id: str | None,
    source_code: str | None,
    source_name: str | None,
    source_type: str | None,
    url: str | None,
    reliability: str | None,
    status: str | None,
    provenance: Mapping[str, Any],
) -> ParticipantSourceLink | None:
    if not (source_id or source_code or source_name or url):
        return None
    return ParticipantSourceLink(
        source_id=source_id,
        source_code=source_code,
        source_name=source_name,
        source_type=source_type,
        url=url,
        reliability=reliability,
        status=status,
        provenance=MappingProxyType(dict(provenance)),
    )


def _region_from_value(value: Any) -> ParticipantRegionCoverage | None:
    country = _as_string(_value(value, "country"))
    region = _as_string(_value(value, "region"))
    city = _as_string(_value(value, "city"))
    address = _as_string(_value(value, "address"))
    if not (country or region or city or address):
        return None
    return ParticipantRegionCoverage(country=country, region=region, city=city, address=address)


def _infer_material_ref_type(material_ref: Any) -> str:
    if _value(material_ref, "supplierName", "supplier"):
        return "supplier"
    if _value(material_ref, "manufacturerName", "manufacturer"):
        return "manufacturer"
    if _value(material_ref, "brandName", "brand"):
        return "brand"
    return "unknown"


def _duplicate_keys(participants: tuple[MaterialParticipantRecord, ...]) -> tuple[str, ...]:
    counts: dict[str, int] = {}
    for participant in participants:
        counts[participant.stable_key] = counts.get(participant.stable_key, 0) + 1
    return tuple(key for key, count in counts.items() if count > 1)


def _dedupe_regions(regions: tuple[ParticipantRegionCoverage, ...]) -> tuple[ParticipantRegionCoverage, ...]:
    return tuple(dict.fromkeys(regions))


def _dedupe_source_links(links: tuple[ParticipantSourceLink, ...]) -> tuple[ParticipantSourceLink, ...]:
    return tuple(dict.fromkeys(links))


def _dedupe_material_links(links: tuple[ParticipantMaterialLink, ...]) -> tuple[ParticipantMaterialLink, ...]:
    return tuple(dict.fromkeys(links))


def _dedupe_mappings(items: tuple[Mapping[str, Any], ...]) -> tuple[Mapping[str, Any], ...]:
    result = []
    seen = set()
    for item in items:
        key = tuple(sorted((str(k), str(v)) for k, v in item.items()))
        if key in seen:
            continue
        seen.add(key)
        result.append(MappingProxyType(dict(item)))
    return tuple(result)


def _stable_key(participant_type: str, participant_id: str | None, display_name: str | None) -> str:
    if participant_id:
        return f"{participant_type}:id:{participant_id}"
    return f"{participant_type}:name:{_normalize_key(display_name)}"


def _group_code(canonical_material_view: MaterialCanonicalView) -> str | None:
    group = canonical_material_view.group or {}
    category = canonical_material_view.category or {}
    return _as_string(group.get("code") or group.get("slug") or category.get("slug"))


def _normalize_key(value: Any) -> str:
    text = _as_string(value) or ""
    return "_".join(text.strip().lower().replace("-", "_").split())


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


def _decimal(value: Any) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
