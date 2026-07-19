from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from threading import RLock
import time
from types import MappingProxyType
from typing import Any, Callable, Mapping


UNIT_PURPOSE = "admin_unit_dictionary_read"
CONVERSION_PURPOSE = "admin_conversion_metadata_read"
PACKAGING_PURPOSE = "admin_packaging_read"
RULE_PURPOSE = "admin_extended_rule_read"
_PURPOSE_PROJECTIONS = {
    UNIT_PURPOSE: "units_and_conversions",
    CONVERSION_PURPOSE: "units_and_conversions",
    PACKAGING_PURPOSE: "packaging",
    RULE_PURPOSE: "extended_rules",
}


class Ref3ProjectionError(RuntimeError):
    pass


@dataclass(frozen=True)
class Ref3UnitRecord:
    unit_code: str
    title: str | None
    symbol: str | None
    dimension: str | None
    aliases: tuple[str, ...]
    eligibility_status: str
    legacy_exact: bool
    review_excluded: bool
    compatibility_status: str
    warning_codes: tuple[str, ...]
    runtime_package_id: str
    ref3_approval_id: str
    ref3_approval_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "aliases": list(self.aliases),
            "compatibility_status": self.compatibility_status,
            "dimension": self.dimension,
            "eligibility_status": self.eligibility_status,
            "eligible_for_catalog_product_write": False,
            "eligible_for_material_write": False,
            "eligible_for_normalizer_output": False,
            "legacy_exact": self.legacy_exact,
            "read_only": True,
            "ref3_approval_id": self.ref3_approval_id,
            "ref3_approval_version": self.ref3_approval_version,
            "review_excluded": self.review_excluded,
            "runtime_package_id": self.runtime_package_id,
            "symbol": self.symbol,
            "title": self.title,
            "unit_code": self.unit_code,
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class Ref3UnitProjection:
    units: tuple[Ref3UnitRecord, ...]
    unit_by_code: Mapping[str, Ref3UnitRecord]
    counts: Mapping[str, int]
    alias_policy: Mapping[str, Any]

    def page(self, *, offset: int, limit: int) -> tuple[Ref3UnitRecord, ...]:
        return self.units[offset : offset + limit]

    def get(self, unit_code: str) -> Ref3UnitRecord | None:
        return self.unit_by_code.get(str(unit_code or "").strip())


@dataclass(frozen=True)
class Ref3ConversionRecord:
    conversion_code: str
    source_unit_code: str
    target_unit_code: str
    conversion_kind: str
    multiplier: Any
    offset: Any
    parameters_required: bool
    required_parameters: tuple[str, ...]
    formula_metadata: Mapping[str, Any] | None
    material_group: str | None
    warning_codes: tuple[str, ...]
    runtime_package_id: str
    ref3_approval_id: str
    ref3_approval_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "conversion_code": self.conversion_code,
            "conversion_kind": self.conversion_kind,
            "executable": False,
            "formula_metadata": dict(self.formula_metadata) if self.formula_metadata else None,
            "legacy_executor_source_of_truth": True,
            "material_group": self.material_group,
            "multiplier": self.multiplier,
            "offset": self.offset,
            "parameters_required": self.parameters_required,
            "read_only": True,
            "ref3_approval_id": self.ref3_approval_id,
            "ref3_approval_version": self.ref3_approval_version,
            "required_parameters": list(self.required_parameters),
            "runtime_package_id": self.runtime_package_id,
            "source_unit_code": self.source_unit_code,
            "target_unit_code": self.target_unit_code,
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class Ref3ConversionProjection:
    conversions: tuple[Ref3ConversionRecord, ...]
    counts: Mapping[str, int]

    def filtered(
        self,
        *,
        source_unit_code: str | None,
        target_unit_code: str | None,
        conversion_kind: str | None,
    ) -> tuple[Ref3ConversionRecord, ...]:
        source = str(source_unit_code or "").strip() or None
        target = str(target_unit_code or "").strip() or None
        kind = str(conversion_kind or "").strip() or None
        return tuple(
            item
            for item in self.conversions
            if (source is None or item.source_unit_code == source)
            and (target is None or item.target_unit_code == target)
            and (kind is None or item.conversion_kind == kind)
        )


@dataclass(frozen=True)
class Ref3UnitsAndConversionsProjection:
    units: Ref3UnitProjection
    conversions: Ref3ConversionProjection


@dataclass(frozen=True)
class Ref3PackagingRecord:
    material_type_code: str
    material_type_title: str
    profile_code: str | None
    profile_title: str | None
    package_type: str | None
    quantity_basis: tuple[str, ...]
    physical_unit: str | None
    commercial_price_basis: tuple[str, ...]
    assignment_eligible: bool
    review_excluded: bool
    mismatch_warning: bool
    mismatch_codes: tuple[str, ...]
    warning_codes: tuple[str, ...]
    runtime_package_id: str
    ref3_approval_id: str
    ref3_approval_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "assignment_eligible": self.assignment_eligible,
            "commercial_price_basis": list(self.commercial_price_basis),
            "eligible_for_export": False,
            "eligible_for_price_basis": False,
            "eligible_for_write": False,
            "material_type_code": self.material_type_code,
            "material_type_title": self.material_type_title,
            "mismatch_codes": list(self.mismatch_codes),
            "mismatch_warning": self.mismatch_warning,
            "package_type": self.package_type,
            "physical_unit": self.physical_unit,
            "profile_code": self.profile_code,
            "profile_title": self.profile_title,
            "quantity_basis": list(self.quantity_basis),
            "read_only": True,
            "ref3_approval_id": self.ref3_approval_id,
            "ref3_approval_version": self.ref3_approval_version,
            "review_excluded": self.review_excluded,
            "runtime_package_id": self.runtime_package_id,
            "warning_codes": list(self.warning_codes),
        }


@dataclass(frozen=True)
class Ref3PackagingProjection:
    assignments: tuple[Ref3PackagingRecord, ...]
    counts: Mapping[str, int]

    def filtered(
        self,
        *,
        material_type_code: str | None,
        profile_code: str | None,
    ) -> tuple[Ref3PackagingRecord, ...]:
        material = str(material_type_code or "").strip() or None
        profile = str(profile_code or "").strip() or None
        return tuple(
            item
            for item in self.assignments
            if (material is None or item.material_type_code == material)
            and (profile is None or item.profile_code == profile)
        )

@dataclass(frozen=True)
class Ref3RuleRecord:
    rule_code: str
    title: str
    rule_class: str
    inputs: tuple[Mapping[str, Any], ...]
    outputs: tuple[Mapping[str, Any], ...]
    unit_contracts: Mapping[str, tuple[str, ...]]
    required_parameters: tuple[str, ...]
    classification: str
    formula_metadata: Mapping[str, Any]
    consumer_status: str
    warning_codes: tuple[str, ...]
    runtime_package_id: str
    ref3_approval_id: str
    ref3_approval_version: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "classification": self.classification,
            "consumer_status": self.consumer_status,
            "executable": False,
            "formula_metadata": dict(self.formula_metadata),
            "inputs": [dict(item) for item in self.inputs],
            "module2_execution_allowed": False,
            "module5_execution_allowed": False,
            "object_scope_allowed": False,
            "outputs": [dict(item) for item in self.outputs],
            "read_only": True,
            "ref3_approval_id": self.ref3_approval_id,
            "ref3_approval_version": self.ref3_approval_version,
            "ref6_required_for_work_execution": True,
            "required_parameters": list(self.required_parameters),
            "rule_class": self.rule_class,
            "rule_code": self.rule_code,
            "runtime_package_id": self.runtime_package_id,
            "title": self.title,
            "unit_contracts": {key: list(value) for key, value in self.unit_contracts.items()},
            "warning_codes": list(self.warning_codes),
            "work_scope_allowed": False,
        }


@dataclass(frozen=True)
class Ref3RuleProjection:
    rules: tuple[Ref3RuleRecord, ...]
    rule_by_code: Mapping[str, Ref3RuleRecord]
    counts: Mapping[str, int]

    def filtered(self, *, rule_class: str | None) -> tuple[Ref3RuleRecord, ...]:
        kind = str(rule_class or "").strip() or None
        return tuple(item for item in self.rules if kind is None or item.rule_class == kind)

    def get(self, rule_code: str) -> Ref3RuleRecord | None:
        return self.rule_by_code.get(str(rule_code or "").strip())


class Ref3ProjectionCache:
    max_entries = 5

    def __init__(
        self,
        *,
        artifact_dir: Path,
        artifact_hashes: Mapping[str, str],
        runtime_package_id: str,
        ref1_approval_id: str,
        ref2_approval_id: str,
        ref3_approval_id: str,
        ref3_approval_version: str,
        legacy_unit_codes: tuple[str, ...],
    ) -> None:
        self._artifact_dir = Path(artifact_dir)
        self._artifact_hashes = MappingProxyType(dict(artifact_hashes))
        self.runtime_package_id = runtime_package_id
        self.ref1_approval_id = ref1_approval_id
        self.ref2_approval_id = ref2_approval_id
        self.ref3_approval_id = ref3_approval_id
        self.ref3_approval_version = ref3_approval_version
        self._legacy_unit_codes = frozenset(legacy_unit_codes)
        self._entries: dict[tuple[str, str, str], Any] = {}
        self._metrics: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    @property
    def cache_entry_count(self) -> int:
        with self._lock:
            return len(self._entries)

    def metrics(self) -> Mapping[str, Mapping[str, Any]]:
        with self._lock:
            return MappingProxyType(
                {
                    purpose: MappingProxyType(dict(values))
                    for purpose, values in sorted(self._metrics.items())
                }
            )

    def get_units(self, purpose: str) -> Ref3UnitProjection:
        bundle = self._get(purpose, self._build_units_and_conversions)
        if not isinstance(bundle, Ref3UnitsAndConversionsProjection):
            raise Ref3ProjectionError("Invalid units projection cache entry")
        return bundle.units

    def get_conversions(self, purpose: str) -> Ref3ConversionProjection:
        bundle = self._get(purpose, self._build_units_and_conversions)
        if not isinstance(bundle, Ref3UnitsAndConversionsProjection):
            raise Ref3ProjectionError("Invalid conversions projection cache entry")
        return bundle.conversions

    def get_packaging(self, purpose: str) -> Ref3PackagingProjection:
        projection = self._get(purpose, self._build_packaging)
        if not isinstance(projection, Ref3PackagingProjection):
            raise Ref3ProjectionError("Invalid packaging projection cache entry")
        return projection

    def get_rules(self, purpose: str) -> Ref3RuleProjection:
        projection = self._get(purpose, self._build_rules)
        if not isinstance(projection, Ref3RuleProjection):
            raise Ref3ProjectionError("Invalid rules projection cache entry")
        return projection

    def _get(self, purpose: str, builder: Callable[[], Any]) -> Any:
        expected_projection = _PURPOSE_PROJECTIONS.get(purpose)
        if expected_projection is None:
            raise Ref3ProjectionError("REF-3 projection purpose is not approved")
        key = (self.runtime_package_id, self.ref3_approval_id, purpose)
        started = time.perf_counter()
        with self._lock:
            self._verify_projection_artifacts(expected_projection)
            cached = self._entries.get(key)
            if cached is not None:
                metric = self._metrics[purpose]
                metric["cache_hits"] += 1
                metric["cached_request_duration_ms"] = (time.perf_counter() - started) * 1000
                return cached
            if len(self._entries) >= self.max_entries:
                raise Ref3ProjectionError("REF-3 projection cache limit reached")
            build_started = time.perf_counter()
            completed = builder()
            size_bytes = len(
                json.dumps(
                    _projection_payload(completed),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
            )
            self._entries[key] = completed
            self._metrics[purpose] = {
                "build_count": 1,
                "cache_hits": 0,
                "first_load_duration_ms": (time.perf_counter() - build_started) * 1000,
                "cached_request_duration_ms": None,
                "serialized_size_bytes": size_bytes,
            }
            return completed

    def _verify_projection_artifacts(self, projection_name: str) -> None:
        names = {
            "units_and_conversions": ("units.json", "conversions.json", "compatibility.json"),
            "packaging": ("packaging.json", "compatibility.json", "taxonomy.json"),
            "extended_rules": ("rules_metadata.json",),
        }[projection_name]
        key_by_name = {
            "units.json": "units",
            "conversions.json": "conversions",
            "packaging.json": "packaging",
            "rules_metadata.json": "rules",
            "compatibility.json": "compatibility",
            "taxonomy.json": "taxonomy",
        }
        for name in names:
            expected = self._artifact_hashes.get(key_by_name[name])
            path = self._artifact_dir / name
            if expected is None or not path.is_file() or _sha256_file(path) != expected:
                raise Ref3ProjectionError(f"REF-3 projection artifact validation failed: {name}")

    def _read_artifact(self, name: str) -> dict[str, Any]:
        payload = json.loads((self._artifact_dir / name).read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or payload.get("artifact_set_id") != self.runtime_package_id:
            raise Ref3ProjectionError(f"Invalid REF-3 projection artifact: {name}")
        return payload

    def _build_units_and_conversions(self) -> Ref3UnitsAndConversionsProjection:
        units_payload = self._read_artifact("units.json")
        conversions_payload = self._read_artifact("conversions.json")
        compatibility = self._read_artifact("compatibility.json")
        unit_records = _unique_records(units_payload.get("units"), "code", "units")
        review_codes = frozenset(
            compatibility.get("review_exclusions", {}).get("ref3_unit_codes", [])
        )
        exact_eligible = frozenset(
            compatibility.get("units", {}).get("exact_runtime_units", [])
        )
        ref_only_eligible = frozenset(
            compatibility.get("units", {}).get("ref_only_units", [])
        )
        all_codes = set(unit_records) | set(review_codes)
        if (
            len(unit_records) != 73
            or len(review_codes) != 17
            or len(all_codes) != 90
            or len(self._legacy_unit_codes) != 16
            or len(exact_eligible) != 14
            or exact_eligible != set(unit_records) & self._legacy_unit_codes
            or len(all_codes & self._legacy_unit_codes) != 16
            or set(unit_records) != set(exact_eligible) | set(ref_only_eligible)
            or not {"linear_meter", "m2_mm"}.issubset(review_codes)
        ):
            raise Ref3ProjectionError("REF-3 unit count or review contract mismatch")
        alias_rules = compatibility.get("units", {}).get("special_alias_rules", [])
        lm_rule = next(
            (item for item in alias_rules if item.get("alias") == "lm"),
            None,
        )
        if (
            not isinstance(lm_rule, Mapping)
            or lm_rule.get("canonical_owner_meaning") != "lumen"
            or lm_rule.get("automatic_mapping_allowed") is not False
        ):
            raise Ref3ProjectionError("REF-3 lm/linear_meter policy mismatch")

        units: list[Ref3UnitRecord] = []
        for code in sorted(all_codes):
            raw = unit_records.get(code, {})
            review = code in review_codes
            legacy = code in self._legacy_unit_codes
            warnings: list[str] = []
            if review:
                warnings.append("REF3_UNIT_REVIEW_EXCLUDED")
            elif not legacy:
                warnings.append("REF_ONLY_ADMIN_METADATA")
            if code == "lm":
                warnings.append("LEGACY_LM_CONTEXT_REQUIRED")
            if code == "linear_meter":
                warnings.append("LINEAR_METER_REVIEW_EXCLUDED")
            if code == "m2_mm":
                warnings.append("M2_MM_REVIEW_EXCLUDED")
            units.append(
                Ref3UnitRecord(
                    unit_code=code,
                    title=_text(raw.get("label_ru")),
                    symbol=_text(raw.get("symbol")),
                    dimension=_text(raw.get("dimension")),
                    aliases=tuple(str(value) for value in raw.get("aliases", [])),
                    eligibility_status="review_excluded" if review else "eligible",
                    legacy_exact=legacy,
                    review_excluded=review,
                    compatibility_status=(
                        "review_excluded_legacy_exact"
                        if review and legacy
                        else "review_excluded"
                        if review
                        else "legacy_exact"
                        if legacy
                        else "ref_only"
                    ),
                    warning_codes=tuple(warnings),
                    runtime_package_id=self.runtime_package_id,
                    ref3_approval_id=self.ref3_approval_id,
                    ref3_approval_version=self.ref3_approval_version,
                )
            )
        unit_tuple = tuple(units)
        unit_projection = Ref3UnitProjection(
            units=unit_tuple,
            unit_by_code=MappingProxyType(
                {item.unit_code: item for item in unit_tuple}
            ),
            counts=MappingProxyType(
                {
                    "eligible": 73,
                    "legacy_exact_eligible": 14,
                    "legacy_exact_source": 16,
                    "review_excluded": 17,
                    "runtime_units": 16,
                    "total": 90,
                }
            ),
            alias_policy=MappingProxyType(
                {
                    "automatic_legacy_lm_mapping_allowed": False,
                    "canonical_lm_meaning": "lumen",
                    "canonical_output_for_linear_meter": "linear_meter",
                    "legacy_lm_to_linear_meter": "context_required",
                    "linear_meter_canonical_code": "linear_meter",
                    "review_excluded_codes": ("linear_meter", "m2_mm"),
                }
            ),
        )

        conversion_rows = conversions_payload.get("conversions", [])
        if not isinstance(conversion_rows, list) or len(conversion_rows) != 47:
            raise Ref3ProjectionError("REF-3 conversion count mismatch")
        kind_counts: Counter[str] = Counter()
        conversions: list[Ref3ConversionRecord] = []
        for raw in conversion_rows:
            if not isinstance(raw, Mapping):
                raise Ref3ProjectionError("Invalid REF-3 conversion record")
            source_type = str(raw.get("source_type"))
            kind = {
                "simple": "simple",
                "technical": "technical",
                "seed": "formula",
            }.get(source_type)
            if kind is None or raw.get("executable") is not False:
                raise Ref3ProjectionError("Executable or unknown REF-3 conversion")
            kind_counts[kind] += 1
            warnings = {
                "simple": ("REF3_CONVERSION_METADATA_ONLY",),
                "technical": ("TECHNICAL_PARAMETERS_REQUIRED",),
                "formula": ("FORMULA_METADATA_NOT_EXECUTABLE",),
            }[kind]
            formula = _text(raw.get("formula"))
            conversions.append(
                Ref3ConversionRecord(
                    conversion_code=str(raw.get("source_code")),
                    source_unit_code=str(raw.get("from_unit")),
                    target_unit_code=str(raw.get("to_unit")),
                    conversion_kind=kind,
                    multiplier=raw.get("factor") if kind == "simple" else None,
                    offset=None,
                    parameters_required=kind != "simple",
                    required_parameters=tuple(
                        str(value) for value in raw.get("required_parameters", [])
                    ),
                    formula_metadata=(
                        MappingProxyType(
                            {"expression": formula, "verified_execution": False}
                        )
                        if formula
                        else None
                    ),
                    material_group=_text(raw.get("material_group")),
                    warning_codes=warnings,
                    runtime_package_id=self.runtime_package_id,
                    ref3_approval_id=self.ref3_approval_id,
                    ref3_approval_version=self.ref3_approval_version,
                )
            )
        if kind_counts != {"simple": 12, "technical": 28, "formula": 7}:
            raise Ref3ProjectionError("REF-3 conversion classification mismatch")
        conversion_tuple = tuple(
            sorted(conversions, key=lambda item: item.conversion_code)
        )
        conversion_projection = Ref3ConversionProjection(
            conversions=conversion_tuple,
            counts=MappingProxyType(
                {
                    "executable": 0,
                    "formula": 7,
                    "simple": 12,
                    "technical": 28,
                    "total": 47,
                }
            ),
        )
        return Ref3UnitsAndConversionsProjection(
            unit_projection,
            conversion_projection,
        )

    def _build_packaging(self) -> Ref3PackagingProjection:
        packaging = self._read_artifact("packaging.json")
        compatibility = self._read_artifact("compatibility.json")
        taxonomy = self._read_artifact("taxonomy.json")
        profiles = _unique_records(
            packaging.get("profiles"),
            "profile_id",
            "packaging profiles",
        )
        eligible = _unique_records(
            packaging.get("assignments"),
            "material_type_id",
            "packaging assignments",
        )
        material_types = _unique_records(
            taxonomy.get("material_types"),
            "code",
            "material types",
        )
        review_codes = frozenset(
            compatibility.get("review_exclusions", {}).get(
                "ref3_packaging_material_types",
                [],
            )
        )
        mismatch_rows = compatibility.get("diagnostics", {}).get(
            "packaging_ref2_mismatches",
            [],
        )
        if not isinstance(mismatch_rows, list):
            raise Ref3ProjectionError("Invalid packaging mismatch diagnostics")
        mismatches: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
        for row in mismatch_rows:
            if isinstance(row, Mapping) and row.get("material_type_id"):
                mismatches[str(row["material_type_id"])].append(row)
        mismatch_codes = frozenset(mismatches)
        excluded = review_codes | mismatch_codes
        if (
            len(profiles) != 21
            or len(eligible) != 633
            or len(material_types) != 978
            or len(review_codes) != 51
            or len(mismatch_rows) != 345
            or len(mismatch_codes) != 316
            or len(review_codes & mismatch_codes) != 22
            or len(excluded) != 345
            or bool(set(eligible) & excluded)
            or set(eligible) | excluded != set(material_types)
        ):
            raise Ref3ProjectionError(
                "REF-3 packaging count or overlap contract mismatch"
            )

        records: list[Ref3PackagingRecord] = []
        for material_code in sorted(material_types):
            assignment = eligible.get(material_code)
            mismatch_items = mismatches.get(material_code, [])
            profile_candidates = {
                str(item.get("packaging_profile_id"))
                for item in mismatch_items
                if item.get("packaging_profile_id")
            }
            if assignment is not None:
                profile_code = _text(assignment.get("packaging_profile_id"))
            elif len(profile_candidates) == 1:
                profile_code = next(iter(profile_candidates))
            elif not profile_candidates:
                profile_code = None
            else:
                raise Ref3ProjectionError(
                    f"Ambiguous packaging profile: {material_code}"
                )
            profile = profiles.get(profile_code, {}) if profile_code else {}
            mismatch_types = tuple(
                sorted(
                    {
                        str(item.get("mismatch_type"))
                        for item in mismatch_items
                        if item.get("mismatch_type")
                    }
                )
            )
            warnings: list[str] = []
            if material_code in review_codes:
                warnings.append("REF3_PACKAGING_REVIEW_EXCLUDED")
            if mismatch_types:
                warnings.append("PACKAGING_REF2_MISMATCH_DIAGNOSTIC_ONLY")
            candidate_basis = (
                tuple(
                    str(value)
                    for value in assignment.get(
                        "candidate_price_basis_units",
                        [],
                    )
                )
                if assignment is not None
                else tuple(
                    str(value)
                    for value in profile.get("allowed_price_basis_units", [])
                )
            )
            quantity_basis = tuple(
                str(value)
                for value in profile.get("primary_quantity_units", [])
            )
            package_units = tuple(
                str(value)
                for value in profile.get("allowed_package_units", [])
            )
            records.append(
                Ref3PackagingRecord(
                    material_type_code=material_code,
                    material_type_title=str(
                        material_types[material_code].get("name_ru")
                        or material_code
                    ),
                    profile_code=profile_code,
                    profile_title=_text(profile.get("name_ru")),
                    package_type=package_units[0] if package_units else None,
                    quantity_basis=quantity_basis,
                    physical_unit=quantity_basis[0] if quantity_basis else None,
                    commercial_price_basis=candidate_basis,
                    assignment_eligible=assignment is not None,
                    review_excluded=material_code in review_codes,
                    mismatch_warning=bool(mismatch_types),
                    mismatch_codes=mismatch_types,
                    warning_codes=tuple(warnings),
                    runtime_package_id=self.runtime_package_id,
                    ref3_approval_id=self.ref3_approval_id,
                    ref3_approval_version=self.ref3_approval_version,
                )
            )
        record_tuple = tuple(records)
        return Ref3PackagingProjection(
            assignments=record_tuple,
            counts=MappingProxyType(
                {
                    "affected_material_types": 316,
                    "assignments": 978,
                    "eligible": 633,
                    "mismatches": 345,
                    "profiles": 21,
                    "review_excluded": 51,
                    "review_mismatch_overlap": 22,
                }
            ),
        )

    def _build_rules(self) -> Ref3RuleProjection:
        payload = self._read_artifact("rules_metadata.json")
        geometry_rows = payload.get("geometry_rules", [])
        extended_rows = payload.get("extended_rules", [])
        if not isinstance(geometry_rows, list) or not isinstance(extended_rows, list):
            raise Ref3ProjectionError("Invalid REF-3 rule artifact")
        geometry_ids = {
            str(item.get("rule_id"))
            for item in geometry_rows
            if isinstance(item, Mapping)
        }
        extended_ids = {
            str(item.get("rule_id"))
            for item in extended_rows
            if isinstance(item, Mapping)
        }
        rules: list[Ref3RuleRecord] = []
        class_counts: Counter[str] = Counter()
        classification_counts: Counter[str] = Counter()
        for raw in [*geometry_rows, *extended_rows]:
            if not isinstance(raw, Mapping) or raw.get("executable") is not False:
                raise Ref3ProjectionError("Executable or invalid REF-3 rule")
            rule_code = str(raw.get("rule_id"))
            semantic = str(raw.get("semantic_type"))
            if rule_code in geometry_ids:
                rule_class = "geometry"
            elif semantic in {"coverage_rate", "package_coverage"}:
                rule_class = "coverage"
            elif semantic == "package_yield":
                rule_class = "yield"
            else:
                rule_class = "consumption"
            if semantic == "operational_consumption":
                classification = "review_only"
                consumer_status = "review_only"
                warnings = ("REF3_RULE_REVIEW_ONLY",)
            elif rule_code == "weight_length_conversion" or rule_code in extended_ids:
                classification = "requires_module2_parameters"
                consumer_status = "module2_parameters_required"
                warnings = ("MODULE2_PARAMETERS_REQUIRED",)
            else:
                classification = "pure_conversion_candidate"
                consumer_status = "module1_metadata_only"
                warnings = ("REF3_RULE_METADATA_ONLY",)
            inputs = tuple(
                MappingProxyType(dict(item))
                for item in raw.get("formula_inputs", [])
                if isinstance(item, Mapping)
            )
            outputs = tuple(
                MappingProxyType(dict(item))
                for item in raw.get("formula_outputs", [])
                if isinstance(item, Mapping)
            )
            required_parameters = tuple(
                str(item.get("name"))
                for item in inputs
                if item.get("source")
                in {
                    "external_scope",
                    "external_quantity",
                    "technology_condition",
                    "selected_material_field",
                }
                and item.get("name")
            )
            input_units = tuple(
                sorted(
                    {
                        str(item.get("unit_code"))
                        for item in inputs
                        if item.get("unit_code")
                    }
                )
            )
            output_units = tuple(
                sorted(
                    {
                        str(item.get("unit_code"))
                        for item in outputs
                        if item.get("unit_code")
                    }
                )
            )
            rules.append(
                Ref3RuleRecord(
                    rule_code=rule_code,
                    title=str(raw.get("name_ru") or rule_code),
                    rule_class=rule_class,
                    inputs=inputs,
                    outputs=outputs,
                    unit_contracts=MappingProxyType(
                        {"inputs": input_units, "outputs": output_units}
                    ),
                    required_parameters=required_parameters,
                    classification=classification,
                    formula_metadata=MappingProxyType(
                        {
                            "expression": _text(raw.get("formula")),
                            "hint": _text(raw.get("formula_hint")),
                            "evaluated": False,
                        }
                    ),
                    consumer_status=consumer_status,
                    warning_codes=warnings,
                    runtime_package_id=self.runtime_package_id,
                    ref3_approval_id=self.ref3_approval_id,
                    ref3_approval_version=self.ref3_approval_version,
                )
            )
            class_counts[rule_class] += 1
            classification_counts[classification] += 1
        if (
            len(rules) != 15
            or class_counts
            != {"geometry": 7, "coverage": 2, "yield": 1, "consumption": 5}
            or classification_counts
            != {
                "pure_conversion_candidate": 6,
                "requires_module2_parameters": 7,
                "review_only": 2,
            }
            or payload.get("executable_rule_count") != 0
            or payload.get("object_work_quantity_calculations") != 0
        ):
            raise Ref3ProjectionError(
                "REF-3 rule classification contract mismatch"
            )
        rule_tuple = tuple(sorted(rules, key=lambda item: item.rule_code))
        return Ref3RuleProjection(
            rules=rule_tuple,
            rule_by_code=MappingProxyType(
                {item.rule_code: item for item in rule_tuple}
            ),
            counts=MappingProxyType(
                {
                    "consumption": 5,
                    "coverage": 2,
                    "executable": 0,
                    "geometry": 7,
                    "pure_candidates": 6,
                    "requires_module2_parameters": 7,
                    "review_only": 2,
                    "total": 15,
                    "yield": 1,
                }
            ),
        )


def _projection_payload(projection: Any) -> Any:
    if isinstance(projection, Ref3UnitsAndConversionsProjection):
        return {
            "units": [item.as_dict() for item in projection.units.units],
            "conversions": [
                item.as_dict() for item in projection.conversions.conversions
            ],
        }
    if isinstance(projection, Ref3PackagingProjection):
        return [item.as_dict() for item in projection.assignments]
    if isinstance(projection, Ref3RuleProjection):
        return [item.as_dict() for item in projection.rules]
    raise Ref3ProjectionError("Unsupported REF-3 projection payload")


def _unique_records(
    value: Any,
    key: str,
    label: str,
) -> dict[str, Mapping[str, Any]]:
    if not isinstance(value, list):
        raise Ref3ProjectionError(f"Invalid {label}")
    records: dict[str, Mapping[str, Any]] = {}
    for item in value:
        if not isinstance(item, Mapping) or not item.get(key):
            raise Ref3ProjectionError(f"Invalid {label} record")
        code = str(item[key])
        if code in records:
            raise Ref3ProjectionError(f"Duplicate {label} record: {code}")
        records[code] = item
    return records


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
