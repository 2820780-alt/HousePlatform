from __future__ import annotations

import json
from pathlib import Path

from tools.module1_ref_projection import CompatibilityClassification, RefPackageLoader
from tools.module1_ref_projection.cli import run as run_projection_cli
from tools.module1_ref_projection.loader import DEFAULT_PACKAGE_FILES
from tools.module1_ref_projection.models import IssueSeverity, ProjectionEntity


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
MATERIAL_SEED = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"


def _write_package(path: Path, package_id: str, version: str = "0.1-draft") -> None:
    path.write_text(
        json.dumps(
            {
                "package_id": package_id,
                "version": version,
                "status": "draft_for_user_review",
                "integration_allowed": False,
                "items": [{"id": f"{package_id.lower()}_item"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def _write_all_packages(reference_root: Path) -> None:
    for package_id, filename in DEFAULT_PACKAGE_FILES.items():
        _write_package(reference_root / filename, package_id)


def test_valid_package_envelope_loads_actual_ref_sources() -> None:
    summary = RefPackageLoader(REFERENCE_ROOT).load()

    loaded_ids = {source.package_id for source in summary.sources}

    assert {"REF-1", "REF-2A", "REF-2B", "REF-3A", "REF-3B", "REF-3C"}.issubset(loaded_ids)
    assert all(issue.severity is not IssueSeverity.BLOCKER for issue in summary.issues)


def test_missing_package_is_reported_without_side_effects(tmp_path: Path) -> None:
    _write_all_packages(tmp_path)
    missing_path = tmp_path / DEFAULT_PACKAGE_FILES["REF-3C"]
    missing_path.unlink()

    summary = RefPackageLoader(tmp_path).load()

    assert any(issue.code == "REF_MISSING_FILE" and issue.package_id == "REF-3C" for issue in summary.issues)
    assert not missing_path.exists()


def test_invalid_json_is_reported(tmp_path: Path) -> None:
    _write_all_packages(tmp_path)
    broken_path = tmp_path / DEFAULT_PACKAGE_FILES["REF-2A"]
    broken_path.write_text("{not-json", encoding="utf-8")

    summary = RefPackageLoader(tmp_path).load()

    assert any(issue.code == "REF_MALFORMED_JSON" and issue.package_id == "REF-2A" for issue in summary.issues)


def test_unsupported_version_is_reported(tmp_path: Path) -> None:
    _write_all_packages(tmp_path)
    _write_package(tmp_path / DEFAULT_PACKAGE_FILES["REF-1"], "REF-1", version="9.9-unknown")

    summary = RefPackageLoader(tmp_path).load()

    assert any(issue.code == "REF_UNSUPPORTED_VERSION" and issue.package_id == "REF-1" for issue in summary.issues)


def test_duplicate_id_is_reported(tmp_path: Path) -> None:
    _write_all_packages(tmp_path)
    duplicate_path = tmp_path / DEFAULT_PACKAGE_FILES["REF-3A"]
    duplicate_path.write_text(
        json.dumps(
            {
                "package_id": "REF-3A",
                "version": "0.3-draft",
                "status": "draft_for_user_review",
                "integration_allowed": False,
                "units": [{"unit_code": "m"}, {"unit_code": "m"}],
            }
        ),
        encoding="utf-8",
    )

    summary = RefPackageLoader(tmp_path).load()

    assert any(issue.code == "REF_DUPLICATE_ID" and issue.entity_id == "m" for issue in summary.issues)


def test_neutral_models_expose_required_statuses() -> None:
    entity = ProjectionEntity(
        entity_id="runtime-only-example",
        entity_type="unit",
        source_package_id="REF-3A",
        classification=CompatibilityClassification.RUNTIME_ONLY,
    )

    assert entity.as_dict()["classification"] == "RUNTIME_ONLY"
    assert {item.value for item in CompatibilityClassification} == {
        "EXACT_MATCH",
        "ALIAS_MATCH",
        "RUNTIME_ONLY",
        "REF_ONLY",
        "AMBIGUOUS",
        "REVIEW_REQUIRED",
        "STRUCTURE_MISMATCH",
        "INVALID_REFERENCE",
        "UNSUPPORTED",
        "INCOMPATIBLE_TYPE",
        "INCOMPATIBLE_UNIT",
        "STRUCTURALLY_COMPATIBLE",
        "UNIT_MISSING",
        "REVERSE_MISSING",
        "DIMENSION_CONFLICT",
        "FORMULA_REQUIRED",
        "PARAMETER_REQUIRED",
        "UNSAFE",
    }


def test_cli_writes_deterministic_output_only_to_output_dir(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    output_dir = tmp_path / "out"
    reference_root.mkdir()
    _write_all_packages(reference_root)

    first = run_projection_cli(reference_root, output_dir)
    first_text = (output_dir / "foundation_summary.json").read_text(encoding="utf-8")
    second = run_projection_cli(reference_root, output_dir)
    second_text = (output_dir / "foundation_summary.json").read_text(encoding="utf-8")

    assert first == second
    assert first_text == second_text
    assert sorted(path.name for path in output_dir.iterdir()) == ["foundation_summary.json"]


def test_tooling_does_not_change_runtime_registries(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    output_dir = tmp_path / "out"
    reference_root.mkdir()
    _write_all_packages(reference_root)
    before = MATERIAL_SEED.read_bytes()

    run_projection_cli(reference_root, output_dir)

    assert MATERIAL_SEED.read_bytes() == before


def test_production_does_not_import_ref_projection_tooling_or_reference_data() -> None:
    production_roots = [PROJECT_ROOT / "app", PROJECT_ROOT / "src"]
    hits: list[str] = []
    for root in production_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if "module1_ref_projection" in text or "docs/Modules/module1/reference_data" in text:
                hits.append(str(path.relative_to(PROJECT_ROOT)))

    assert hits == []
