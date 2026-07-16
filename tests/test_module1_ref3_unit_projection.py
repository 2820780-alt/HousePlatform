from __future__ import annotations

import json
from pathlib import Path

from tools.module1_ref_projection import CompatibilityClassification
from tools.module1_ref_projection.cli import run as run_projection_cli
from tools.module1_ref_projection.ref3_units import REF3A_FILENAME, project_ref3_units, write_ref3_unit_projection_outputs

PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
MATERIAL_SEED = PROJECT_ROOT / "src" / "modules" / "module1" / "seeds" / "material_knowledge_seed.json"
UNIT_SERVICE = PROJECT_ROOT / "app" / "services" / "module1_unit_conversion_registry.py"


def _write_ref3a(reference_root: Path, units: list[dict[str, object]], review_queue: list[dict[str, object]] | None = None) -> None:
    reference_root.mkdir(parents=True, exist_ok=True)
    (reference_root / REF3A_FILENAME).write_text(json.dumps({"package_id": "REF-3A", "version": "0.3-draft", "status": "draft_for_user_review", "approval": {"integration_allowed": False}, "units": units, "review_queue": review_queue or []}, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_runtime_seed(path: Path, unit_conversions: list[dict[str, object]] | None = None) -> None:
    path.write_text(json.dumps({"unitConversions": unit_conversions or []}, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_unit_service(path: Path, *, aliases: dict[str, tuple[str, ...]], simple: dict[tuple[str, str], object] | None = None, technical: dict[tuple[str, str, str], tuple[tuple[str, ...], ...]] | None = None) -> None:
    path.write_text("from decimal import Decimal\n" f"UNIT_ALIASES = {aliases!r}\n" f"SIMPLE_CONVERSION_FACTORS = {simple or {}!r}\n" f"TECHNICAL_REQUIREMENT_SETS = {technical or {}!r}\n", encoding="utf-8")


def _unit(code: str, dimension: str, aliases: list[str] | None = None, base: str | None = None) -> dict[str, object]:
    return {"unit_code": code, "label_ru": code, "symbol": code, "dimension": dimension, "base_unit_code": base or code, "aliases": aliases or [code], "status": "active_draft"}


def _conversion_entities(result) -> dict[str, object]:
    return {entity.entity_id: entity for entity in result.conversion_matrix}


def _unit_entities(result) -> dict[str, object]:
    return {entity.entity_id: entity for entity in result.unit_matrix}


def test_actual_ref3_unit_projection_counts_match_audit_checkpoints() -> None:
    result = project_ref3_units(REFERENCE_ROOT)

    assert result.counts["ref_units"] == 90
    assert result.counts["runtime_units"] == 16
    assert result.counts["exact"] == 16
    assert result.counts["ref_only"] == 74
    assert result.counts["runtime_only"] == 0
    assert result.counts["review_required_units"] == 17
    assert result.counts["review_auto_activatable"] == 0
    assert result.counts["runtime_conversion_simple"] == 12
    assert result.counts["runtime_conversion_technical"] == 28
    assert result.counts["runtime_conversion_seed"] == 7
    assert result.counts["runtime_conversion_records"] == 47
    assert result.counts["dimension_conflicts"] == 0
    assert result.counts["formula_required"] == 7
    assert result.counts["parameter_required"] == 28
    assert result.counts["blockers"] == 0


def test_exact_missing_alias_collision_dimension_conflict_and_reverse_diagnostics(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_seed = tmp_path / "seed.json"
    runtime_service = tmp_path / "unit_service.py"
    _write_ref3a(reference_root, [_unit("m", "length", ["m", "meter"]), _unit("cm", "length", ["cm"]), _unit("kg", "mass", ["kg"]), _unit("shared_a", "custom", ["shared"]), _unit("shared_b", "custom", ["shared"]), _unit("ref_only", "custom", ["ref_only"])])
    _write_runtime_seed(runtime_seed)
    _write_unit_service(runtime_service, aliases={"m": ("m",), "cm": ("cm",), "kg": ("kg",), "runtime_only": ("runtime_only",)}, simple={("m", "cm"): 100, ("m", "kg"): 1})

    result = project_ref3_units(reference_root, runtime_seed, runtime_service)
    units = _unit_entities(result)
    conversions = _conversion_entities(result)

    assert units["m"].classification is CompatibilityClassification.EXACT_MATCH
    assert units["ref_only"].classification is CompatibilityClassification.REF_ONLY
    assert units["runtime_only"].classification is CompatibilityClassification.RUNTIME_ONLY
    assert any(issue.code == "REF3_ALIAS_COLLISION" and issue.entity_id == "shared" for issue in result.issues)
    assert conversions["simple:m->cm"].classification is CompatibilityClassification.REVERSE_MISSING
    assert conversions["simple:m->kg"].classification is CompatibilityClassification.DIMENSION_CONFLICT


def test_formula_parameter_required_and_review_isolation(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_seed = tmp_path / "seed.json"
    runtime_service = tmp_path / "unit_service.py"
    review_unit = _unit("piece", "count", ["piece"])
    _write_ref3a(reference_root, [_unit("m", "length"), _unit("kg", "mass"), _unit("m3", "volume"), review_unit], review_queue=[review_unit])
    _write_runtime_seed(runtime_seed, [{"group": "board", "from": "piece", "to": "m3", "formula": "pieces * volume_m3"}])
    _write_unit_service(runtime_service, aliases={"m": ("m",), "kg": ("kg",), "m3": ("m3",), "piece": ("piece",)}, technical={("rebar", "m", "kg"): (("kg_per_meter",),)})

    result = project_ref3_units(reference_root, runtime_seed, runtime_service)
    units = _unit_entities(result)
    conversions = _conversion_entities(result)

    assert units["piece"].classification is CompatibilityClassification.REVIEW_REQUIRED
    assert units["piece"].payload["auto_activatable"] is False
    assert conversions["technical:rebar:m->kg"].classification is CompatibilityClassification.PARAMETER_REQUIRED
    assert conversions["seed:board:piece->m3"].classification is CompatibilityClassification.FORMULA_REQUIRED


def test_ref3_outputs_are_deterministic(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    runtime_seed = tmp_path / "seed.json"
    runtime_service = tmp_path / "unit_service.py"
    first_output = tmp_path / "first"
    second_output = tmp_path / "second"
    _write_ref3a(reference_root, [_unit("m", "length"), _unit("cm", "length")])
    _write_runtime_seed(runtime_seed)
    _write_unit_service(runtime_service, aliases={"m": ("m",), "cm": ("cm",)}, simple={("m", "cm"): 100, ("cm", "m"): 0.01})

    write_ref3_unit_projection_outputs(reference_root, first_output, runtime_seed, runtime_service)
    write_ref3_unit_projection_outputs(reference_root, second_output, runtime_seed, runtime_service)

    expected = ["ref3_conversion_matrix.json", "ref3_unit_matrix.json", "ref3_units_issues.json", "ref3_units_report.md", "ref3_units_summary.json"]
    assert sorted(path.name for path in first_output.iterdir()) == expected
    assert {path.name: path.read_text(encoding="utf-8") for path in first_output.iterdir()} == {path.name: path.read_text(encoding="utf-8") for path in second_output.iterdir()}


def test_cli_generates_ref3_unit_outputs_only_when_requested(tmp_path: Path) -> None:
    reference_root = tmp_path / "reference"
    output_dir = tmp_path / "out"
    runtime_seed = tmp_path / "seed.json"
    runtime_service = tmp_path / "unit_service.py"
    _write_ref3a(reference_root, [_unit("m", "length")])
    _write_runtime_seed(runtime_seed)
    _write_unit_service(runtime_service, aliases={"m": ("m",)})

    payload = run_projection_cli(reference_root, output_dir, include_ref3_units=True, runtime_taxonomy_path=runtime_seed, runtime_unit_service_path=runtime_service)

    assert payload["ref3_units"]["counts"]["ref_units"] == 1
    assert sorted(path.name for path in output_dir.iterdir()) == ["foundation_summary.json", "ref3_conversion_matrix.json", "ref3_unit_matrix.json", "ref3_units_issues.json", "ref3_units_report.md", "ref3_units_summary.json"]


def test_ref3_unit_projection_does_not_change_runtime_registries() -> None:
    seed_before = MATERIAL_SEED.read_bytes()
    service_before = UNIT_SERVICE.read_bytes()

    project_ref3_units(REFERENCE_ROOT)

    assert MATERIAL_SEED.read_bytes() == seed_before
    assert UNIT_SERVICE.read_bytes() == service_before


def test_production_does_not_import_ref3_projection_tooling_or_reference_data() -> None:
    production_roots = [PROJECT_ROOT / "app", PROJECT_ROOT / "src"]
    hits: list[str] = []
    for root in production_roots:
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8-sig")
            if "module1_ref_projection" in text or "ATOM_REF3_" in text or "docs/Modules/module1/reference_data" in text:
                hits.append(str(path.relative_to(PROJECT_ROOT)))

    assert hits == []
