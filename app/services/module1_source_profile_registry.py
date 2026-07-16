from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.module1_extraction_blueprint_registry import (
    ExtractionBlueprintRegistry,
    KEY_BLUEPRINT_GROUPS,
)
from app.services.module1_material_seed_registry import (
    MaterialKnowledgeSeedRegistry,
    get_material_knowledge_seed_registry,
)
from app.services.module1_unit_conversion_registry import UnitConversionRegistry


SOURCE_TYPES = ("supplier_site", "manufacturer_site", "api", "file", "manual")
ALLOWED_OBJECT_TYPES = ("materials", "prices", "documents", "availability")


SOURCE_TARGET_GROUPS: Mapping[str, tuple[str, ...]] = {
    "BAUCENTER": KEY_BLUEPRINT_GROUPS,
    "YUFO_VKBLOCK": ("aerated_concrete_block",),
    "YUFO_KSMK_GAZOBETON_KRASNODAR": ("aerated_concrete_block",),
    "YUFO_SST_KVIK": ("gypsum_plaster", "aerated_concrete_block"),
    "YUFO_KROVLYA_IZOLYACIYA": ("metal_tile", "mineral_wool_slab"),
    "YUFO_ROOF_MATERIALS": ("metal_tile", "mineral_wool_slab"),
    "YUFO_DOSKA_BRUS": ("board",),
    "YUFO_PROFI_LES": ("board",),
    "YUFO_1METALLOBAZA_KRASNODAR": ("rebar",),
    "YUFO_SPK_KRASNODAR": ("rebar", "metal_tile"),
    "YUFO_YUGKABEL": ("cable",),
    "SUPPLIER_FILE_UPLOAD": KEY_BLUEPRINT_GROUPS,
    "MANUAL_MATERIAL_ENTRY": KEY_BLUEPRINT_GROUPS,
}

SOURCE_DEFINITIONS: Mapping[str, Mapping[str, Any]] = {
    "BAUCENTER": {
        "display_name": "Baucenter",
        "source_type": "supplier_site",
        "base_url": "https://baucenter.ru/",
        "region": None,
        "city": None,
        "reliability": "test",
        "linked_participant": None,
        "status": "test",
    },
    "YUFO_VKBLOCK": {
        "display_name": "VKBlock",
        "source_type": "manufacturer_site",
        "base_url": "https://vkblock.ru/",
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "manufacturer",
        "status": "test",
    },
    "YUFO_KSMK_GAZOBETON_KRASNODAR": {
        "display_name": "KSMK Aerated Concrete Krasnodar",
        "source_type": "manufacturer_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": "Krasnodar",
        "reliability": "test",
        "linked_participant": "manufacturer",
        "status": "needs_base_url",
    },
    "YUFO_SST_KVIK": {
        "display_name": "SST KVIK",
        "source_type": "manufacturer_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "manufacturer",
        "status": "needs_base_url",
    },
    "YUFO_KROVLYA_IZOLYACIYA": {
        "display_name": "Roofing and Insulation",
        "source_type": "supplier_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "needs_base_url",
    },
    "YUFO_ROOF_MATERIALS": {
        "display_name": "Roof Materials",
        "source_type": "supplier_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "needs_base_url",
    },
    "YUFO_DOSKA_BRUS": {
        "display_name": "Board and Timber",
        "source_type": "supplier_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "needs_base_url",
    },
    "YUFO_PROFI_LES": {
        "display_name": "Profi Les",
        "source_type": "supplier_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "needs_base_url",
    },
    "YUFO_1METALLOBAZA_KRASNODAR": {
        "display_name": "1 Metallobaza Krasnodar",
        "source_type": "supplier_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": "Krasnodar",
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "needs_base_url",
    },
    "YUFO_SPK_KRASNODAR": {
        "display_name": "SPK Krasnodar",
        "source_type": "supplier_site",
        "base_url": None,
        "region": "Krasnodar krai / Southern Federal District",
        "city": "Krasnodar",
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "needs_base_url",
    },
    "YUFO_YUGKABEL": {
        "display_name": "YugKabel",
        "source_type": "supplier_site",
        "base_url": "https://yugkabel.ru/",
        "region": "Krasnodar krai / Southern Federal District",
        "city": None,
        "reliability": "test",
        "linked_participant": "supplier",
        "status": "test",
    },
    "SUPPLIER_FILE_UPLOAD": {
        "display_name": "Supplier file upload",
        "source_type": "file",
        "base_url": None,
        "region": None,
        "city": None,
        "reliability": "normal",
        "linked_participant": "supplier",
        "status": "active",
    },
    "MANUAL_MATERIAL_ENTRY": {
        "display_name": "Manual material entry",
        "source_type": "manual",
        "base_url": None,
        "region": None,
        "city": None,
        "reliability": "normal",
        "linked_participant": None,
        "status": "active",
    },
}

CATEGORY_MAPPING: Mapping[str, tuple[str, ...]] = {
    "aerated_concrete_block": ("gas block", "gazobeton", "wall blocks", "aerated concrete"),
    "gypsum_board_regular": ("gkl", "plasterboard", "drywall"),
    "gypsum_board_moisture_resistant": ("gypsum board",),
    "rebar": ("rebar", "reinforcement", "steel bars", "armature"),
    "ready_mix_concrete": ("ready mix concrete", "concrete", "rbu"),
    "gypsum_plaster": ("dry mix", "plaster", "gypsum plaster"),
    "deep_penetration_primer": ("primer", "deep penetration primer"),
    "porcelain_tile": ("porcelain tile", "tile", "gres"),
    "metal_tile": ("metal tile", "roofing", "roof sheet"),
    "board": ("board", "timber", "lumber"),
    "mineral_wool_slab": ("mineral wool", "insulation", "slab insulation"),
    "cable": ("cable", "wire", "electrics"),
}


@dataclass(frozen=True)
class Module1SourceProfile:
    source_code: str
    display_name: str
    source_type: str
    base_url: str | None
    region: str | None
    city: str | None
    reliability: str
    allowed_objects: tuple[str, ...]
    linked_participant: str | None
    status: str
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class Module1ExtractionProfile:
    source_code: str
    profile_code: str
    target_material_groups: tuple[str, ...]
    blueprint_refs: tuple[str, ...]
    field_mapping_rules: Mapping[str, Mapping[str, tuple[str, ...]]]
    unit_mapping_rules: Mapping[str, Mapping[str, tuple[str, ...]]]
    category_mapping_rules: Mapping[str, tuple[str, ...]]
    price_extraction_rules: Mapping[str, tuple[str, ...]]
    characteristic_extraction_rules: Mapping[str, tuple[str, ...]]
    document_extraction_hints: Mapping[str, tuple[str, ...]]
    pagination_hints: Mapping[str, Any]
    product_card_hints: Mapping[str, Any]
    confidence_defaults: Mapping[str, float]
    adapter_compatibility_notes: tuple[str, ...]


@dataclass(frozen=True)
class ProfileValidationReport:
    is_valid: bool
    missing_fields: tuple[str, ...]
    invalid_fields: tuple[str, ...]
    message: str


@dataclass(frozen=True)
class SourceProfileReadinessReport:
    source_code: str
    has_source_profile: bool
    has_extraction_profile: bool
    target_material_groups: tuple[str, ...]
    missing_blueprints: tuple[str, ...]
    has_field_mappings: bool
    has_unit_mappings: bool
    has_document_hints: bool
    not_configured: tuple[str, ...]
    ready: bool
    message: str


class Module1SourceProfileRegistry:
    def __init__(
        self,
        seed_registry: MaterialKnowledgeSeedRegistry | None = None,
        blueprint_registry: ExtractionBlueprintRegistry | None = None,
        unit_registry: UnitConversionRegistry | None = None,
    ) -> None:
        self._seed_registry = seed_registry or get_material_knowledge_seed_registry()
        self._blueprint_registry = blueprint_registry or ExtractionBlueprintRegistry(self._seed_registry)
        self._unit_registry = unit_registry or UnitConversionRegistry(self._seed_registry)

    def get_source_profile(self, source_code: str) -> Module1SourceProfile | None:
        source_key = _source_key(source_code)
        definition = SOURCE_DEFINITIONS.get(source_key)
        if definition is None:
            return None
        return Module1SourceProfile(
            source_code=source_key,
            display_name=str(definition["display_name"]),
            source_type=str(definition["source_type"]),
            base_url=definition.get("base_url"),
            region=definition.get("region"),
            city=definition.get("city"),
            reliability=str(definition["reliability"]),
            allowed_objects=ALLOWED_OBJECT_TYPES,
            linked_participant=definition.get("linked_participant"),
            status=str(definition["status"]),
            notes=(
                "Read-only profile. It describes extraction configuration and does not run parsing.",
                "SourceAdapter must write raw ingestion candidates, not canonical Material directly.",
            ),
        )

    def list_source_profiles(self) -> tuple[Module1SourceProfile, ...]:
        return tuple(
            profile
            for source_code in sorted(SOURCE_DEFINITIONS)
            if (profile := self.get_source_profile(source_code)) is not None
        )

    def get_extraction_profile(
        self,
        source_code: str,
        material_group: str | None = None,
    ) -> Module1ExtractionProfile | None:
        source_key = _source_key(source_code)
        if source_key not in SOURCE_DEFINITIONS:
            return None
        target_groups = SOURCE_TARGET_GROUPS.get(source_key, tuple())
        if material_group is not None:
            resolved_group = self._blueprint_registry.resolve_group_code(material_group)
            if resolved_group not in target_groups:
                return None
            target_groups = (resolved_group,)

        blueprint_refs = tuple(group for group in target_groups if self._blueprint_registry.has_blueprint(group))
        field_mapping_rules = {
            group: self.get_field_mapping(source_key, group)
            for group in target_groups
            if self._blueprint_registry.has_blueprint(group)
        }
        unit_mapping_rules = {
            group: self.get_unit_mapping(source_key, group)
            for group in target_groups
            if self._blueprint_registry.has_blueprint(group)
        }
        category_mapping_rules = {
            group: self.get_category_mapping(source_key, group)
            for group in target_groups
        }
        document_hints = {
            group: self._blueprint_registry.get_document_hints(group)
            for group in target_groups
            if self._blueprint_registry.has_blueprint(group)
        }
        characteristic_rules = {
            group: tuple(
                dict.fromkeys(
                    self._blueprint_registry.get_required_extraction_fields(group)
                    + self._blueprint_registry.get_module2_extraction_fields(group)
                )
            )
            for group in target_groups
            if self._blueprint_registry.has_blueprint(group)
        }
        return Module1ExtractionProfile(
            source_code=source_key,
            profile_code=f"{source_key.lower()}_extraction_profile",
            target_material_groups=target_groups,
            blueprint_refs=blueprint_refs,
            field_mapping_rules=field_mapping_rules,
            unit_mapping_rules=unit_mapping_rules,
            category_mapping_rules=category_mapping_rules,
            price_extraction_rules={
                "price": ("price", "raw_price", "cost", "amount"),
                "currency": ("currency", "raw_currency"),
                "unit": ("unit", "raw_unit", "price_unit"),
                "availability": ("availability", "stock", "in_stock"),
            },
            characteristic_extraction_rules=characteristic_rules,
            document_extraction_hints=document_hints,
            pagination_hints={
                "pagination": ("next_page", "page", "offset"),
                "do_not_run": "Registry only describes hints; source adapters own execution.",
            },
            product_card_hints={
                "title": ("title", "name", "product_name"),
                "sku": ("sku", "article", "vendor_code"),
                "detail_url": ("url", "external_url", "href"),
            },
            confidence_defaults={
                "field_mapping": 0.75,
                "unit_mapping": 0.70,
                "category_mapping": 0.65,
                "document_hint": 0.60,
            },
            adapter_compatibility_notes=(
                "Do not create canonical Material from SourceAdapter output.",
                "Adapters should emit raw payloads for RawIngestionItem/CatalogProduct compatibility.",
                "Extraction blueprints from Module 1 define expected fields and document hints.",
            ),
        )

    def list_extraction_profiles(self) -> tuple[Module1ExtractionProfile, ...]:
        return tuple(
            profile
            for source_code in sorted(SOURCE_DEFINITIONS)
            if (profile := self.get_extraction_profile(source_code)) is not None
        )

    def get_allowed_objects(self, source_code: str) -> tuple[str, ...]:
        profile = self.get_source_profile(source_code)
        return profile.allowed_objects if profile else tuple()

    def get_target_material_groups(self, source_code: str) -> tuple[str, ...]:
        source_key = _source_key(source_code)
        return SOURCE_TARGET_GROUPS.get(source_key, tuple())

    def get_field_mapping(self, source_code: str, material_group: str) -> Mapping[str, tuple[str, ...]]:
        if self.get_source_profile(source_code) is None:
            return {}
        blueprint = self._blueprint_registry.get_blueprint(material_group)
        return blueprint.field_aliases if blueprint else {}

    def get_unit_mapping(self, source_code: str, material_group: str) -> Mapping[str, tuple[str, ...]]:
        if self.get_source_profile(source_code) is None:
            return {}
        blueprint = self._blueprint_registry.get_blueprint(material_group)
        if blueprint is None:
            return {}
        aliases = self._unit_registry.get_unit_aliases()
        return {
            unit: aliases[unit]
            for unit in blueprint.unit_hints
            if unit in aliases
        }

    def get_category_mapping(self, source_code: str, material_group: str) -> tuple[str, ...]:
        if self.get_source_profile(source_code) is None:
            return tuple()
        resolved_group = self._blueprint_registry.resolve_group_code(material_group)
        return CATEGORY_MAPPING.get(resolved_group, tuple())

    def validate_source_profile(self, profile: Module1SourceProfile | Mapping[str, Any] | None) -> ProfileValidationReport:
        data = _profile_data(profile)
        missing = tuple(field for field in ("source_code", "source_type", "allowed_objects", "status") if not data.get(field))
        invalid: list[str] = []
        source_type = data.get("source_type")
        if source_type and source_type not in SOURCE_TYPES:
            invalid.append("source_type")
        allowed_objects = tuple(data.get("allowed_objects") or tuple())
        if any(item not in ALLOWED_OBJECT_TYPES for item in allowed_objects):
            invalid.append("allowed_objects")
        return ProfileValidationReport(
            is_valid=not missing and not invalid,
            missing_fields=missing,
            invalid_fields=tuple(invalid),
            message="Source profile is valid." if not missing and not invalid else "Source profile is incomplete.",
        )

    def validate_extraction_profile(
        self,
        profile: Module1ExtractionProfile | Mapping[str, Any] | None,
    ) -> ProfileValidationReport:
        data = _profile_data(profile)
        missing = tuple(
            field
            for field in ("source_code", "target_material_groups", "field_mapping_rules", "unit_mapping_rules")
            if not data.get(field)
        )
        invalid: list[str] = []
        for group in tuple(data.get("target_material_groups") or tuple()):
            if not self._blueprint_registry.has_blueprint(group):
                invalid.append(f"blueprint:{group}")
        return ProfileValidationReport(
            is_valid=not missing and not invalid,
            missing_fields=missing,
            invalid_fields=tuple(invalid),
            message="Extraction profile is valid." if not missing and not invalid else "Extraction profile is incomplete.",
        )

    def build_profile_readiness_report(self, source_code: str) -> SourceProfileReadinessReport:
        source_profile = self.get_source_profile(source_code)
        extraction_profile = self.get_extraction_profile(source_code)
        source_key = _source_key(source_code)
        if source_profile is None:
            return SourceProfileReadinessReport(
                source_code=source_key,
                has_source_profile=False,
                has_extraction_profile=False,
                target_material_groups=tuple(),
                missing_blueprints=tuple(),
                has_field_mappings=False,
                has_unit_mappings=False,
                has_document_hints=False,
                not_configured=("source_profile", "extraction_profile"),
                ready=False,
                message="Source profile is not registered.",
            )

        target_groups = extraction_profile.target_material_groups if extraction_profile else tuple()
        missing_blueprints = tuple(group for group in target_groups if not self._blueprint_registry.has_blueprint(group))
        has_field_mappings = bool(extraction_profile and extraction_profile.field_mapping_rules)
        has_unit_mappings = bool(extraction_profile and extraction_profile.unit_mapping_rules)
        has_document_hints = bool(extraction_profile and extraction_profile.document_extraction_hints)
        not_configured = tuple(
            section
            for section, missing in (
                ("extraction_profile", extraction_profile is None),
                ("target_material_groups", not target_groups),
                ("extraction_blueprints", bool(missing_blueprints)),
                ("field_mappings", not has_field_mappings),
                ("unit_mappings", not has_unit_mappings),
                ("document_hints", not has_document_hints),
            )
            if missing
        )
        ready = bool(extraction_profile and target_groups and not missing_blueprints and has_field_mappings and has_unit_mappings and has_document_hints)
        return SourceProfileReadinessReport(
            source_code=source_profile.source_code,
            has_source_profile=True,
            has_extraction_profile=extraction_profile is not None,
            target_material_groups=target_groups,
            missing_blueprints=missing_blueprints,
            has_field_mappings=has_field_mappings,
            has_unit_mappings=has_unit_mappings,
            has_document_hints=has_document_hints,
            not_configured=not_configured,
            ready=ready,
            message="Source profile is ready for raw ingestion planning." if ready else "Source profile needs configuration before ingestion.",
        )


def get_module1_source_profile_registry() -> Module1SourceProfileRegistry:
    return Module1SourceProfileRegistry()


def get_source_profile(source_code: str) -> Module1SourceProfile | None:
    return get_module1_source_profile_registry().get_source_profile(source_code)


def list_source_profiles() -> tuple[Module1SourceProfile, ...]:
    return get_module1_source_profile_registry().list_source_profiles()


def get_extraction_profile(source_code: str, material_group: str | None = None) -> Module1ExtractionProfile | None:
    return get_module1_source_profile_registry().get_extraction_profile(source_code, material_group)


def list_extraction_profiles() -> tuple[Module1ExtractionProfile, ...]:
    return get_module1_source_profile_registry().list_extraction_profiles()


def get_allowed_objects(source_code: str) -> tuple[str, ...]:
    return get_module1_source_profile_registry().get_allowed_objects(source_code)


def get_target_material_groups(source_code: str) -> tuple[str, ...]:
    return get_module1_source_profile_registry().get_target_material_groups(source_code)


def get_field_mapping(source_code: str, material_group: str) -> Mapping[str, tuple[str, ...]]:
    return get_module1_source_profile_registry().get_field_mapping(source_code, material_group)


def get_unit_mapping(source_code: str, material_group: str) -> Mapping[str, tuple[str, ...]]:
    return get_module1_source_profile_registry().get_unit_mapping(source_code, material_group)


def get_category_mapping(source_code: str, material_group: str) -> tuple[str, ...]:
    return get_module1_source_profile_registry().get_category_mapping(source_code, material_group)


def validate_source_profile(profile: Module1SourceProfile | Mapping[str, Any] | None) -> ProfileValidationReport:
    return get_module1_source_profile_registry().validate_source_profile(profile)


def validate_extraction_profile(
    profile: Module1ExtractionProfile | Mapping[str, Any] | None,
) -> ProfileValidationReport:
    return get_module1_source_profile_registry().validate_extraction_profile(profile)


def build_profile_readiness_report(source_code: str) -> SourceProfileReadinessReport:
    return get_module1_source_profile_registry().build_profile_readiness_report(source_code)


def _source_key(source_code: str) -> str:
    return str(source_code).strip().upper()


def _profile_data(profile: Module1SourceProfile | Module1ExtractionProfile | Mapping[str, Any] | None) -> Mapping[str, Any]:
    if profile is None:
        return {}
    if isinstance(profile, Mapping):
        return profile
    return profile.__dict__
