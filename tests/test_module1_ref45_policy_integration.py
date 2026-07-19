from __future__ import annotations

from decimal import Decimal
import json
from pathlib import Path
import shutil

import pytest
from pydantic import ValidationError

from app.config import Settings, settings
from app.services.module1_alternatives_analogs import list_alternative_rules
from app.services.module1_material_normalizer import build_normalization_report, infer_material_group, normalize_raw_ingestion_item
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem
from app.services.module1_ref4_normalization_policy import (
    DEFAULT_APPROVAL_PATH,
    DEFAULT_ARTIFACT_DIR,
    Module1Ref45ConfigurationError,
    require_module1_ref45_runtime,
    resolve_ref4_alias,
    validate_module1_ref45_runtime,
)
from app.services.module1_ref5_compatibility_policy import (
    evaluate_ref5_compatibility,
    list_ref5_context_rules,
    list_ref5_substitution_policies,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _raw(title: str, *, category: str | None = None, price: object = Decimal("100")) -> Module1RawIngestionItem:
    return Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="BAUCENTER",
        raw_title=title,
        raw_category=category,
        raw_unit="шт",
        raw_price=price,
        raw_characteristics={},
        raw_manufacturer="Test manufacturer",
        source_url="https://example.test/material",
    )


def test_ref45_mode_contract_defaults_to_legacy_and_rejects_unknown() -> None:
    assert settings.MODULE1_REF45_MODE == "legacy"
    assert validate_module1_ref45_runtime("legacy").is_valid is True
    with pytest.raises(Module1Ref45ConfigurationError, match="Unsupported"):
        validate_module1_ref45_runtime("unexpected")
    with pytest.raises(ValidationError):
        Settings(MODULE1_REF45_MODE="unexpected")


def test_approved_runtime_loads_pinned_artifact_and_approval() -> None:
    activation = validate_module1_ref45_runtime("approved")

    assert activation.is_valid is True
    assert activation.artifact_set_id == "ref45-runtime-v1-5fe5e067d0dd"
    assert activation.approval_id == "ref45-activation-v1-5fe5e067d0dd"
    assert activation.counts["ref4_alias_rules"] == 89
    assert activation.counts["ref5_substitution_rules"] == 13
    assert len(activation.alias_rules) == 89
    assert len(activation.material_type_profiles) == 978


def test_invalid_artifact_and_approval_fail_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact"
    approval = tmp_path / "approval_manifest.json"
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact)
    shutil.copy2(DEFAULT_APPROVAL_PATH, approval)
    (artifact / "ref4_alias_rules.json").write_text("{}\n", encoding="utf-8")

    invalid_artifact = validate_module1_ref45_runtime(
        "approved", artifact_dir=artifact, approval_path=approval, allowed_root=tmp_path
    )
    assert invalid_artifact.is_valid is False
    assert any("HASH_INVALID" in issue.code for issue in invalid_artifact.issues)

    shutil.rmtree(artifact)
    shutil.copytree(DEFAULT_ARTIFACT_DIR, artifact)
    payload = json.loads(approval.read_text(encoding="utf-8"))
    payload["activation_flags"]["automatic_replacement_allowed"] = True
    approval.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    invalid_approval = validate_module1_ref45_runtime(
        "approved", artifact_dir=artifact, approval_path=approval, allowed_root=tmp_path
    )
    assert invalid_approval.is_valid is False
    assert any(issue.code == "APPROVAL_HASH_INVALID" for issue in invalid_approval.issues)


def test_trusted_global_aliases_resolve_without_fuzzy_matching() -> None:
    gas = resolve_ref4_alias("Газоблок D500 600x300x200", mode="approved")
    osb = resolve_ref4_alias("ОСП 12 мм", mode="approved")

    assert (gas.state, gas.material_type_id) == ("trusted_match", "aerated_concrete_block")
    assert (osb.state, osb.material_type_id) == ("trusted_match", "osb_board")
    assert gas.preserve_dimensions_and_grade_tokens is True


def test_scoped_alias_requires_exact_scope_before_automatic_resolution() -> None:
    without_scope = resolve_ref4_alias("gas block", mode="approved")
    with_scope = resolve_ref4_alias("gas block", scope="aerated_concrete_block", mode="approved")

    assert without_scope.state == "context_required"
    assert without_scope.automatic_resolution_allowed is False
    assert with_scope.state == "scoped_trusted_match"
    assert with_scope.material_type_id == "aerated_concrete_block"


@pytest.mark.parametrize(
    "alias",
    ["гкл", "минвата", "каменная вата", "эппс", "профлист", "водосток", "пароизоляция", "ветрозащита", "фитинг", "проф труба", "tile", "roofing", "board", "insulation"],
)
def test_generic_aliases_never_auto_resolve_subtype(alias: str) -> None:
    result = resolve_ref4_alias(alias, mode="approved")

    assert result.state in {"context_required", "review_required"}
    assert result.material_type_id is None
    assert result.automatic_resolution_allowed is False


@pytest.mark.parametrize(
    ("value", "rule_id"),
    [("gkl", "legacy_alias_060"), ("plasterboard", "legacy_alias_061"), ("drywall", "legacy_alias_062")],
)
def test_corrected_gkl_source_rules_are_regular_scoped_but_non_automatic(value: str, rule_id: str) -> None:
    result = resolve_ref4_alias(value, scope="gypsum_board_regular", mode="approved")

    assert result.alias_rule_id == rule_id
    assert result.scope == "gypsum_board_regular"
    assert result.legacy_normalized_value == "gypsum_board_regular"
    assert result.state == "context_required"
    assert result.material_type_id is None
    assert result.automatic_resolution_allowed is False


def test_unknown_alias_is_safe_and_does_not_create_mapping() -> None:
    result = resolve_ref4_alias("unlisted material 123", mode="approved")

    assert result.state == "unknown"
    assert result.alias_rule_id is None
    assert result.material_type_id is None


def test_normalizer_legacy_output_is_unchanged_and_approved_blocks_generic_gkl(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _raw("ГКЛ 2500x1200x12.5")
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "legacy")
    assert infer_material_group(raw) == "gypsum_board_moisture_resistant"

    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "approved")
    candidate = normalize_raw_ingestion_item(raw)
    assert candidate.suggested_group_code is None
    assert "2500x1200x12.5" in candidate.normalized_title


def test_approved_normalizer_keeps_trusted_resolution_and_price_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "approved")
    candidate = normalize_raw_ingestion_item(_raw("Газоблок D500 600x300x200"))
    no_price = build_normalization_report(_raw("Газоблок D500 600x300x200", price=None))

    assert candidate.suggested_group_code == "aerated_concrete_block"
    assert candidate.normalized_characteristics["length_mm"] == Decimal("600")
    assert no_price.is_ready_for_matching is False
    assert "missing positive price" in no_price.warnings


def test_ref5_counts_active_and_review_policies() -> None:
    context = list_ref5_context_rules(mode="approved")
    all_rules = list_ref5_substitution_policies(mode="approved")
    active = list_ref5_substitution_policies(mode="approved", include_review=False)

    assert len(context) == 15
    assert len(all_rules) == 13
    assert len(active) == 3
    assert sum(item["status"] == "review_required" for item in all_rules) == 10
    assert not any(item["automatic_selection_allowed"] for item in all_rules)
    assert not any(item["automatic_write_allowed"] for item in all_rules)


def test_ref5_forbidden_replacement_is_safety_result() -> None:
    result = evaluate_ref5_compatibility(
        "gypsum_board_moisture_resistant", "gypsum_board_regular", mode="approved"
    )

    assert result.state == "forbidden"
    assert result.allowed_as_candidate is False
    assert result.execution_allowed is False
    assert result.automatic_selection_allowed is False


def test_ref5_same_type_full_analog_requires_equal_complete_fields_and_units() -> None:
    fields = {"diameter_mm": 12, "steel_class": "A500C", "profile_type": "ribbed"}
    complete = evaluate_ref5_compatibility(
        "rebar", "rebar", source_characteristics=fields, target_characteristics=dict(fields), source_unit="kg", target_unit="kg", mode="approved"
    )
    missing = evaluate_ref5_compatibility(
        "rebar", "rebar", source_characteristics={"diameter_mm": 12}, target_characteristics={"diameter_mm": 12}, source_unit="kg", target_unit="kg", mode="approved"
    )
    conflict = evaluate_ref5_compatibility(
        "rebar", "rebar", source_characteristics=fields, target_characteristics={**fields, "diameter_mm": 10}, source_unit="kg", target_unit="piece", mode="approved"
    )

    assert complete.state == "full_analog_candidate"
    assert complete.allowed_as_candidate is True
    assert complete.automatic_selection_allowed is False
    assert missing.state == "review_required" and set(missing.missing_fields) == {"steel_class", "profile_type"}
    assert conflict.state == "review_required" and set(conflict.conflicting_fields) == {"diameter_mm", "unit"}


def test_cement_screed_relation_remains_review_only() -> None:
    result = evaluate_ref5_compatibility("cement_screed", "dry_screed", mode="approved")

    assert result.relation_id == "substitution_rule_007"
    assert result.state == "review_required"
    assert result.execution_allowed is False
    assert result.automatic_write_allowed is False


def test_existing_alternatives_switches_between_legacy_and_three_read_only_rules(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "legacy")
    legacy = list_alternative_rules()
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "approved")
    approved = list_alternative_rules()

    assert len(legacy) > 3
    assert len(approved) == 3
    assert all(rule.module2_hints["module2ExecutionAllowed"] is False for rule in approved)
    assert all(rule.module5_hints["module5ExecutionAllowed"] is False for rule in approved)
    assert all("automatic replacement" in " ".join(rule.warnings).lower() for rule in approved)


def test_rollback_to_legacy_restores_existing_behavior(monkeypatch: pytest.MonkeyPatch) -> None:
    raw = _raw("ГКЛ 2500x1200x12.5")
    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "approved")
    assert infer_material_group(raw) is None
    assert require_module1_ref45_runtime().is_valid is True

    monkeypatch.setattr(settings, "MODULE1_REF45_MODE", "legacy")
    assert infer_material_group(raw) == "gypsum_board_moisture_resistant"
    assert list_ref5_context_rules() == tuple()


def test_production_services_do_not_import_source_docs_or_projection_tools() -> None:
    sources = "\n".join(
        (PROJECT_ROOT / path).read_text(encoding="utf-8")
        for path in (
            "app/services/module1_ref4_normalization_policy.py",
            "app/services/module1_ref5_compatibility_policy.py",
            "app/services/module1_material_normalizer.py",
            "app/services/module1_alternatives_analogs.py",
        )
    )

    assert "docs/Modules" not in sources
    assert "module1_ref_projection" not in sources
    assert "MaterialAlias" not in sources
    assert "MaterialAnalog" not in sources
    assert "session.add" not in sources
    assert "commit(" not in sources