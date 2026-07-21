from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
WORK_CATALOG_PATH = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "work_catalog_seed.json"
REF1_PATH = REFERENCE_ROOT / "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json"
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
ARTIFACT_SET_ID = "ref6-runtime-v1-2256595bd388"
MANIFEST_FILENAME = "manifest.json"
ARTIFACT_FILENAMES = (
    "work_profiles.json",
    "safe_role_hints.json",
    "conditional_role_hints.json",
    "review_queue.json",
    "no_material_works.json",
    "legacy_material_role_evidence.json",
    "consumer_contracts.json",
)
SOURCE_HASHES: Mapping[str, str] = MappingProxyType(
    {
        "ATOM_REF6_Work_Material_Mappings_v1_PRELIMINARY_APPROVED.json": "747bcbf6beea33a127abcb843ec4ae8abcd383f73fbd0192138b9a54703ba20e",
        "ATOM_REF6_Package_Manifest_v1_PRELIMINARY_APPROVED.json": "2256595bd3883192f1458902de48528104464d06e18449f0420e559b650bd2a9",
        "ATOM_REF6_Summary_v1.json": "e6b83371a21f3d0636607d079b1e29137b4dd3ac0f86ec2c06992bd838e1d6e1",
        "ATOM_REF6_Review_v1.md": "d38bc322dc8d09fbb777c4f928d8314da035b14cc3c9109909b6992fa0f7ef21",
        "ATOM_REF6_Approval_Record_v1.md": "5b7fa692aa5d91ea1279cf484963dd40c94afd4aa3be9eeabab8753ef1b850e4",
    }
)
EXPECTED_COUNTS: Mapping[str, int] = MappingProxyType(
    {
        "automatic_database_write_rules": 0,
        "automatic_material_creation_rules": 0,
        "conditional_role_hints": 104,
        "conditional_works": 87,
        "direct_works": 80,
        "existing_material_role_evidence_rows": 42,
        "no_material_works": 39,
        "quantity_rules_activated": 0,
        "ref1_material_types": 978,
        "review_only_role_mappings": 7,
        "review_only_works": 3,
        "review_queue_items": 10,
        "role_mappings": 193,
        "safe_role_hints": 82,
        "sku_selection_rules": 0,
        "work_groups": 24,
        "works": 209,
    }
)
SAFE_EXAMPLES: Mapping[str, str] = MappingProxyType(
    {
        "earthworks_ustroystvo_peschanoy_podushki": "sand",
        "earthworks_ustroystvo_schebenochnoy_podushki": "crushed_stone",
        "earthworks_ukladka_geotekstilya": "geotextile",
        "foundations_concrete_montazh_vintovyh_svay": "screw_pile",
        "roofing_montazh_metallocherepicy": "metal_tile",
        "roofing_montazh_profnastila_na_krovlyu": "profiled_sheet_roofing",
        "roofing_montazh_osb_pod_myagkuyu_krovlyu": "osb_board",
        "electrical_prokladka_kabelya": "cable",
        "floors_screeds_ukladka_laminata": "laminate",
        "fences_gates_montazh_zabora_iz_profnastila": "profiled_sheet_fence",
    }
)
EXPECTED_REVIEW_WORK_CODES = frozenset(
    {
        "bathroom_wet_zones_montazh_ekrana_pod_vannu",
        "earthworks_obratnaya_zasypka",
        "windows_doors_slopes_ustroystvo_dvernyh_otkosov",
        "electrical_montazh_elektricheskoy_tochki",
        "facade_naruzhnye_otkosy",
        "landscaping_ustroystvo_otmostki",
        "sewerage_montazh_tochki_kanalizacii",
        "tile_works_ukladka_plitki_po_diagonali",
        "water_supply_montazh_santehnicheskogo_pribora",
        "water_supply_montazh_tochki_vodosnabzheniya",
    }
)
FORBIDDEN_MAPPING_FLAGS = (
    "catalog_product_selection_allowed",
    "database_write_allowed",
    "material_creation_allowed",
    "module2_execution_allowed",
    "module5_costing_allowed",
    "quantity_calculation_allowed",
    "quantity_formula_activation_allowed",
    "sku_selection_allowed",
)


class Ref6BuildError(ValueError):
    pass


@dataclass(frozen=True)
class Ref6BuildResult:
    artifact_dir: Path
    manifest_path: Path
    artifact_hashes: Mapping[str, str]
    manifest_sha256: str
    counts: Mapping[str, int]
    already_existed: bool


def build_ref6_runtime_artifacts(
    reference_root: str | Path = REFERENCE_ROOT,
    output_root: str | Path = RUNTIME_REFERENCE_ROOT,
    *,
    work_catalog_path: str | Path = WORK_CATALOG_PATH,
    ref1_path: str | Path = REF1_PATH,
) -> Ref6BuildResult:
    source, source_hashes = load_ref6_source_package(reference_root)
    work_catalog = _read_json(Path(work_catalog_path))
    ref1 = _read_json(Path(ref1_path))
    _validate_source_content(source, work_catalog, ref1)
    profiles = sorted(source["work_profiles"], key=lambda item: item["work_code"])
    mappings = source["role_mappings"]
    safe = sorted(
        (item for item in mappings if item["execution_status"] == "SAFE_HINT"),
        key=_mapping_sort_key,
    )
    conditional = sorted(
        (item for item in mappings if item["execution_status"] == "CONDITIONAL_HINT"),
        key=_mapping_sort_key,
    )
    review_mappings = sorted(
        (item for item in mappings if item["execution_status"] == "REVIEW_ONLY"),
        key=_mapping_sort_key,
    )
    review_items = sorted(source["review_queue"], key=lambda item: item["review_id"])
    no_material = [item for item in profiles if item["material_policy"] == "NO_MATERIAL"]
    evidence = sorted(source["existing_material_role_evidence"], key=lambda item: item["evidence_id"])
    documents: dict[str, dict[str, Any]] = {
        "work_profiles.json": {**_header("ref6_work_profiles"), "items": profiles},
        "safe_role_hints.json": {
            **_header("ref6_safe_role_hints"),
            "items": safe,
            "type_hint_execution_allowed": True,
        },
        "conditional_role_hints.json": {
            **_header("ref6_conditional_role_hints"),
            "context_required": True,
            "execution_allowed": False,
            "items": conditional,
        },
        "review_queue.json": {
            **_header("ref6_review_queue"),
            "automatic_approval_allowed": False,
            "items": review_items,
            "mapping_items": review_mappings,
        },
        "no_material_works.json": {
            **_header("ref6_no_material_works"),
            "artificial_material_role_allowed": False,
            "items": no_material,
        },
        "legacy_material_role_evidence.json": {
            **_header("ref6_legacy_material_role_evidence"),
            "automatic_promotion_allowed": False,
            "items": evidence,
        },
        "consumer_contracts.json": {
            **_header("ref6_consumer_contracts"),
            "constitutional_boundaries": source["constitutional_boundaries"],
            "consumer_contracts": source["consumer_contracts"],
            "execution_policy": source["execution_policy"],
        },
    }
    serialized = {name: canonical_json_bytes(documents[name]) for name in ARTIFACT_FILENAMES}
    artifact_hashes = {name: sha256_bytes(content) for name, content in serialized.items()}
    manifest = {
        "artifact_schema_version": "1.0",
        "artifact_set_id": ARTIFACT_SET_ID,
        "artifacts": {
            name: {"sha256": artifact_hashes[name], "size": len(serialized[name])}
            for name in sorted(artifact_hashes)
        },
        "canonical_serialization": canonical_serialization_contract(),
        "counts": dict(EXPECTED_COUNTS),
        "database_write_allowed": False,
        "material_creation_allowed": False,
        "module2_execution_allowed": False,
        "module5_costing_allowed": False,
        "quantity_calculation_allowed": False,
        "ref3_formula_activation_allowed": False,
        "sku_selection_allowed": False,
        "source_package": {
            "package_id": source["package_id"],
            "status": source["status"],
            "version": source["version"],
            "source_hashes": dict(source_hashes),
        },
        "source_snapshots": {
            "ref1_sha256": sha256_file(ref1_path),
            "work_catalog_sha256": sha256_file(work_catalog_path),
        },
        "write_activation_allowed": False,
    }
    serialized[MANIFEST_FILENAME] = canonical_json_bytes(manifest)
    target = Path(output_root) / ARTIFACT_SET_ID
    already_existed = _write_immutable_package(target, serialized)
    validate_ref6_runtime_artifacts(target)
    return Ref6BuildResult(
        artifact_dir=target,
        manifest_path=target / MANIFEST_FILENAME,
        artifact_hashes=MappingProxyType(dict(artifact_hashes)),
        manifest_sha256=sha256_file(target / MANIFEST_FILENAME),
        counts=EXPECTED_COUNTS,
        already_existed=already_existed,
    )


def load_ref6_source_package(
    reference_root: str | Path = REFERENCE_ROOT,
) -> tuple[dict[str, Any], dict[str, str]]:
    root = Path(reference_root)
    hashes: dict[str, str] = {}
    for name, expected in SOURCE_HASHES.items():
        path = root / name
        if not path.is_file():
            raise Ref6BuildError(f"Missing REF-6 source file: {name}")
        actual = sha256_file(path)
        if actual != expected:
            raise Ref6BuildError(f"REF-6 source hash mismatch: {name}")
        hashes[name] = actual
    source = _read_json(root / "ATOM_REF6_Work_Material_Mappings_v1_PRELIMINARY_APPROVED.json")
    manifest = _read_json(root / "ATOM_REF6_Package_Manifest_v1_PRELIMINARY_APPROVED.json")
    summary = _read_json(root / "ATOM_REF6_Summary_v1.json")
    if manifest.get("status") != "preliminary_approved" or source.get("status") != "preliminary_approved":
        raise Ref6BuildError("REF-6 source status is not preliminary_approved")
    if manifest.get("counts") != dict(EXPECTED_COUNTS) or summary.get("counts") != dict(EXPECTED_COUNTS):
        raise Ref6BuildError("REF-6 manifest/summary counts mismatch")
    if not source.get("approval", {}).get("approved_by_user"):
        raise Ref6BuildError("REF-6 source is not user-approved")
    if source.get("approval", {}).get("codex_may_expand_content") is not False:
        raise Ref6BuildError("REF-6 source allows unapproved content expansion")
    return source, hashes


def validate_ref6_runtime_artifacts(path: str | Path) -> dict[str, Any]:
    root = Path(path)
    expected_names = set(ARTIFACT_FILENAMES) | {MANIFEST_FILENAME}
    actual_names = {item.name for item in root.iterdir() if item.is_file()} if root.is_dir() else set()
    if actual_names != expected_names:
        raise Ref6BuildError(f"Runtime artifact file set mismatch: {sorted(actual_names)}")
    manifest = _read_json(root / MANIFEST_FILENAME)
    if manifest.get("artifact_set_id") != ARTIFACT_SET_ID:
        raise Ref6BuildError("Runtime artifact set ID mismatch")
    if manifest.get("counts") != dict(EXPECTED_COUNTS):
        raise Ref6BuildError("Runtime artifact counts mismatch")
    for name in ARTIFACT_FILENAMES:
        metadata = manifest.get("artifacts", {}).get(name)
        if not isinstance(metadata, dict) or metadata.get("sha256") != sha256_file(root / name):
            raise Ref6BuildError(f"Runtime artifact hash mismatch: {name}")
    return manifest


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def canonical_serialization_contract() -> dict[str, Any]:
    return {
        "bom": False,
        "encoding": "UTF-8",
        "ensure_ascii": False,
        "indent": 2,
        "line_ending": "LF",
        "sort_keys": True,
        "trailing_newline": True,
    }


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _validate_source_content(
    source: Mapping[str, Any],
    work_catalog: Mapping[str, Any],
    ref1: Mapping[str, Any],
) -> None:
    if source.get("counts") != dict(EXPECTED_COUNTS):
        raise Ref6BuildError("REF-6 source counts mismatch")
    groups = work_catalog.get("groups", [])
    works = work_catalog.get("works", [])
    profiles = source.get("work_profiles", [])
    mappings = source.get("role_mappings", [])
    review = source.get("review_queue", [])
    evidence = source.get("existing_material_role_evidence", [])
    if len(groups) != 24 or len(works) != 209:
        raise Ref6BuildError("Work Catalog must remain exactly 24 groups / 209 works")
    work_by_code = {item["work_code"]: item for item in works}
    profile_by_code = {item["work_code"]: item for item in profiles}
    if len(work_by_code) != len(works) or len(profile_by_code) != len(profiles):
        raise Ref6BuildError("Duplicate work code detected")
    if set(work_by_code) != set(profile_by_code):
        raise Ref6BuildError("REF-6 work-code parity mismatch")
    for code, profile in profile_by_code.items():
        work = work_by_code[code]
        if (
            profile.get("work_group") != work.get("work_group")
            or profile.get("work_name_ru") != work.get("work_name")
            or profile.get("work_unit") != work.get("default_unit")
        ):
            raise Ref6BuildError(f"REF-6 work profile differs from immutable catalog: {code}")
    classes = Counter(item.get("material_policy") for item in profiles)
    if classes != Counter({"NO_MATERIAL": 39, "DIRECT": 80, "CONDITIONAL": 87, "REVIEW_ONLY": 3}):
        raise Ref6BuildError(f"REF-6 work classification mismatch: {dict(classes)}")
    statuses = Counter(item.get("execution_status") for item in mappings)
    if statuses != Counter({"SAFE_HINT": 82, "CONDITIONAL_HINT": 104, "REVIEW_ONLY": 7}):
        raise Ref6BuildError(f"REF-6 mapping status mismatch: {dict(statuses)}")
    mapping_ids = [item.get("mapping_id") for item in mappings]
    mapping_keys = [
        (item.get("work_code"), item.get("role_code"), tuple(item.get("target_material_type_ids", [])))
        for item in mappings
    ]
    if len(set(mapping_ids)) != len(mapping_ids) or len(set(mapping_keys)) != len(mapping_keys):
        raise Ref6BuildError("Duplicate REF-6 mapping IDs or keys")
    if {item.get("work_code") for item in mappings} - set(work_by_code):
        raise Ref6BuildError("REF-6 mapping references unknown work code")
    material_types = {item["material_type_id"] for item in ref1.get("material_types", [])}
    if len(material_types) != 978:
        raise Ref6BuildError("REF-1 material type count mismatch")
    targets = {target for item in mappings for target in item.get("target_material_type_ids", [])}
    if not targets <= material_types:
        raise Ref6BuildError(f"Unknown REF-1 material type IDs: {sorted(targets - material_types)}")
    for item in mappings:
        if any(item.get(flag) is not False for flag in FORBIDDEN_MAPPING_FLAGS):
            raise Ref6BuildError(f"Forbidden REF-6 mapping flag enabled: {item.get('mapping_id')}")
    if len(review) != 10 or Counter(item.get("review_kind") for item in review) != Counter(
        {"work_classification": 3, "role_mapping": 7}
    ):
        raise Ref6BuildError("REF-6 review queue mismatch")
    if {item.get("work_code") for item in review} != EXPECTED_REVIEW_WORK_CODES:
        raise Ref6BuildError("REF-6 review work-code set mismatch")
    if any(item.get("automatic_approval_allowed") is not False for item in review):
        raise Ref6BuildError("REF-6 review item allows automatic approval")
    if len(evidence) != 42 or any(
        item.get("status") != "evidence_only"
        or item.get("promoted_to_executable_mapping_automatically") is not False
        for item in evidence
    ):
        raise Ref6BuildError("Legacy material-role evidence contract mismatch")
    for work_code, target in SAFE_EXAMPLES.items():
        if not any(
            item.get("work_code") == work_code
            and item.get("execution_status") == "SAFE_HINT"
            and target in item.get("target_material_type_ids", [])
            for item in mappings
        ):
            raise Ref6BuildError(f"Required SAFE_HINT example missing: {work_code} -> {target}")


def _header(artifact_type: str) -> dict[str, Any]:
    return {
        "artifact_schema_version": "1.0",
        "artifact_set_id": ARTIFACT_SET_ID,
        "artifact_type": artifact_type,
        "catalog_product_selection_allowed": False,
        "database_write_allowed": False,
        "material_creation_allowed": False,
        "module2_execution_allowed": False,
        "module5_costing_allowed": False,
        "quantity_calculation_allowed": False,
        "ref3_formula_activation_allowed": False,
        "sku_selection_allowed": False,
    }


def _mapping_sort_key(item: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(item.get("work_code") or ""),
        str(item.get("role_code") or ""),
        str(item.get("mapping_id") or ""),
    )


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Ref6BuildError(f"Cannot read JSON {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise Ref6BuildError(f"Expected object in {path.name}")
    return payload


def _write_immutable_package(target: Path, files: Mapping[str, bytes]) -> bool:
    if target.name != ARTIFACT_SET_ID:
        raise Ref6BuildError("Invalid REF-6 artifact set ID")
    if target.exists():
        existing = {item.name: item.read_bytes() for item in target.iterdir() if item.is_file()}
        if existing != dict(files):
            raise Ref6BuildError(f"Immutable REF-6 package already differs: {target}")
        return True
    target.mkdir(parents=True, exist_ok=False)
    for name in sorted(files):
        (target / name).write_bytes(files[name])
    return False
