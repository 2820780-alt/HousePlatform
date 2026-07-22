from __future__ import annotations

import json
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.services.module1_ref6_work_material_policy import (
    DEFAULT_APPROVAL_PATH,
    DEFAULT_ARTIFACT_DIR,
    EXPECTED_COUNTS,
    Module1Ref6ConfigurationError,
    build_work_material_consumer_contract,
    require_module1_ref6_runtime,
    resolve_work_material_hints,
    validate_module1_ref6_runtime,
)
from app.services.module1_work_catalog import (
    build_governed_work_material_consumer_contract,
    get_work_item,
    resolve_governed_work_material_hints,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_CASES = {
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


def test_mode_defaults_to_legacy_and_unknown_mode_fails_explicitly() -> None:
    assert settings.MODULE1_REF6_MODE == "legacy"
    assert require_module1_ref6_runtime().mode == "legacy"
    with pytest.raises(ValidationError):
        Settings(MODULE1_REF6_MODE="unexpected")
    with pytest.raises(Module1Ref6ConfigurationError):
        require_module1_ref6_runtime("unexpected")


def test_approved_activation_has_exact_counts_and_read_only_boundaries() -> None:
    activation = require_module1_ref6_runtime("approved")
    assert activation.is_valid is True
    assert dict(activation.counts) == dict(EXPECTED_COUNTS)
    assert len(activation.work_profiles) == 209
    assert len(activation.safe_hints) == 82
    assert len(activation.conditional_hints) == 104
    assert len(activation.review_items) == 10
    assert len(activation.review_mappings) == 7
    assert len(activation.no_material_works) == 39
    assert len(activation.legacy_evidence) == 42
    assert activation.as_dict()["database_write_allowed"] is False
    assert activation.as_dict()["module2_execution_allowed"] is False
    assert activation.as_dict()["module5_costing_allowed"] is False


def test_invalid_artifact_and_approval_fail_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "runtime" / DEFAULT_ARTIFACT_DIR.name
    approval = tmp_path / "runtime" / "approvals" / DEFAULT_APPROVAL_PATH.parent.name / "approval_manifest.json"
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact)
    approval.parent.mkdir(parents=True)
    shutil.copy2(DEFAULT_APPROVAL_PATH, approval)
    payload = json.loads((artifact / "safe_role_hints.json").read_text(encoding="utf-8"))
    payload["items"] = payload["items"][:-1]
    (artifact / "safe_role_hints.json").write_text(json.dumps(payload), encoding="utf-8")
    invalid_artifact = validate_module1_ref6_runtime(
        "approved", artifact_dir=artifact, approval_path=approval, allowed_root=tmp_path
    )
    assert invalid_artifact.is_valid is False
    assert any("HASH_INVALID" in item.code for item in invalid_artifact.issues)
    shutil.rmtree(artifact)
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact)
    approval_payload = json.loads(approval.read_text(encoding="utf-8"))
    approval_payload["activation_flags"]["database_write_allowed"] = True
    approval.write_text(json.dumps(approval_payload), encoding="utf-8")
    invalid_approval = validate_module1_ref6_runtime(
        "approved", artifact_dir=artifact, approval_path=approval, allowed_root=tmp_path
    )
    assert invalid_approval.is_valid is False
    assert any(item.code == "APPROVAL_HASH_INVALID" for item in invalid_approval.issues)


@pytest.mark.parametrize(("work_code", "target"), SAFE_CASES.items())
def test_safe_examples_return_type_level_hints_only(work_code: str, target: str) -> None:
    result = resolve_work_material_hints(work_code, mode="approved")
    assert result.state == "safe_hints"
    assert result.known_work is True
    assert result.no_material is False
    assert any(target in item.target_material_type_ids for item in result.hints)
    assert all(item.execution_status == "SAFE_HINT" for item in result.hints)
    assert all(item.type_hint_execution_allowed is True for item in result.hints)
    _assert_forbidden_flags(result.as_dict())
    for hint in result.hints:
        _assert_forbidden_flags(hint.as_dict())


def test_conditional_hint_remains_non_executable_with_or_without_context() -> None:
    code = "walls_masonry_montazh_karkasnoy_steny"
    without_context = resolve_work_material_hints(code, mode="approved")
    with_context = resolve_work_material_hints(
        code, {"wall_height_m": 2.8, "technology": "frame_wall"}, mode="approved"
    )
    assert without_context.state == "conditional_hints"
    assert with_context.state == "conditional_hints"
    assert without_context.context_received is False
    assert with_context.context_received is True
    assert without_context.hints
    assert all(item.execution_status == "CONDITIONAL_HINT" for item in without_context.hints)
    assert all(item.type_hint_execution_allowed is False for item in without_context.hints)
    _assert_forbidden_flags(with_context.as_dict())


@pytest.mark.parametrize(
    "work_code",
    [
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
    ],
)
def test_review_examples_never_auto_approve(work_code: str) -> None:
    result = resolve_work_material_hints(work_code, mode="approved")
    assert result.state == "review_required"
    assert result.review_items
    assert all(item.get("automatic_approval_allowed") is False for item in result.review_items)
    assert all(item.type_hint_execution_allowed is False for item in result.hints)
    _assert_forbidden_flags(result.as_dict())


def test_no_material_and_unknown_work_fail_closed_without_artificial_role() -> None:
    no_material = resolve_work_material_hints(
        "demolition_demontazh_peregorodok_gkl", mode="approved"
    )
    unknown = resolve_work_material_hints("not_a_work_code", mode="approved")
    assert no_material.state == "no_material"
    assert no_material.no_material is True
    assert no_material.hints == tuple()
    assert unknown.state == "unknown_work"
    assert unknown.known_work is False
    assert unknown.hints == tuple()
    _assert_forbidden_flags(no_material.as_dict())
    _assert_forbidden_flags(unknown.as_dict())


def test_legacy_mode_and_additive_work_catalog_wrappers_preserve_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code = "earthworks_ustroystvo_peschanoy_podushki"
    assert get_work_item(code) is not None
    monkeypatch.setattr(settings, "MODULE1_REF6_MODE", "legacy")
    legacy = resolve_governed_work_material_hints(code)
    assert legacy.state == "legacy"
    assert legacy.hints == tuple()
    monkeypatch.setattr(settings, "MODULE1_REF6_MODE", "approved")
    approved = resolve_governed_work_material_hints(code)
    contract = build_governed_work_material_consumer_contract(code)
    assert approved.state == "safe_hints"
    assert contract == build_work_material_consumer_contract(code)
    assert contract["price_data_included"] is False
    assert contract["resolved_material_requirement"] is False
    assert contract["side_effects"] is False


def test_rollback_to_legacy_restores_empty_hint_behavior(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    code = "electrical_prokladka_kabelya"
    monkeypatch.setattr(settings, "MODULE1_REF6_MODE", "approved")
    assert resolve_work_material_hints(code).state == "safe_hints"
    monkeypatch.setattr(settings, "MODULE1_REF6_MODE", "legacy")
    rolled_back = resolve_work_material_hints(code)
    assert rolled_back.state == "legacy"
    assert rolled_back.hints == tuple()


def test_production_service_is_isolated_from_docs_tools_db_and_other_modules() -> None:
    service = (
        PROJECT_ROOT / "app" / "services" / "module1_ref6_work_material_policy.py"
    ).read_text(encoding="utf-8")
    assert "docs/Modules" not in service
    assert "tools.module1_ref_projection" not in service
    assert "sqlalchemy" not in service.lower()
    assert "app.models" not in service
    assert "module2" not in "\n".join(
        line for line in service.splitlines() if line.startswith("from ") or line.startswith("import ")
    )
    assert "module5" not in "\n".join(
        line for line in service.splitlines() if line.startswith("from ") or line.startswith("import ")
    )
    assert "source_task_runner" not in service
    assert "module1_extraction_workbench" not in service


def _assert_forbidden_flags(payload: dict) -> None:
    for field in (
        "catalog_product_selection_allowed",
        "database_write_allowed",
        "material_creation_allowed",
        "module2_execution_allowed",
        "module5_costing_allowed",
        "quantity_calculation_allowed",
        "ref3_formula_activation_allowed",
        "sku_selection_allowed",
    ):
        assert payload[field] is False
