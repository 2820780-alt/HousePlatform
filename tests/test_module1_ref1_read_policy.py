from __future__ import annotations

from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.module1_material_seed_registry import get_material_knowledge_seed_registry
from app.services.module1_ref1_read_policy import (
    APPROVED_PURPOSES,
    DENIED_PURPOSES,
    EXPECTED_APPROVAL_SHA256,
    Module1Ref1ReadActivation,
)
from app.services.module1_ref_runtime_artifacts import (
    SUPPORTED_MODES,
    snapshot_legacy_material_registry,
    validate_module1_ref_runtime,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def activation() -> Module1Ref1ReadActivation:
    result = validate_module1_ref_runtime("ref1_read")
    assert isinstance(result, Module1Ref1ReadActivation)
    assert result.is_valid
    return result


def test_supported_modes_include_ref1_read_while_default_remains_legacy() -> None:
    from app.config import settings

    assert SUPPORTED_MODES == {"legacy", "artifact_validation", "dual_read", "ref1_read", "ref2_read"}
    assert settings.MODULE1_REF_RUNTIME_MODE == "legacy"


def test_activation_is_approved_read_only_and_does_not_mutate_registry(
    activation: Module1Ref1ReadActivation,
) -> None:
    registry = get_material_knowledge_seed_registry()
    before = snapshot_legacy_material_registry(registry)
    second = validate_module1_ref_runtime("ref1_read", registry=registry)

    assert activation.status == second.status == "PASS"
    assert activation.package_validated is activation.approval_validated is True
    assert activation.approval_sha256 == EXPECTED_APPROVAL_SHA256
    assert activation.business_reads_enabled is True
    assert activation.ref_only_writes_enabled is False
    assert activation.registry_mutated is False
    assert activation.database_writes == 0
    assert snapshot_legacy_material_registry(registry) == before


def test_projection_counts_and_immutability(activation: Module1Ref1ReadActivation) -> None:
    assert dict(activation.counts) == {
        "groups": 37,
        "legacy_groups": 19,
        "legacy_material_types": 192,
        "material_types": 978,
        "ref_only_groups": 18,
        "ref_only_material_types": 786,
    }
    assert activation.projection is not None
    assert len(activation.projection.groups) == 37
    assert len(activation.projection.material_types) == 978
    with pytest.raises(FrozenInstanceError):
        activation.mode = "legacy"  # type: ignore[misc]


def test_exact_purpose_allowlist_and_unknown_purpose_deny(
    activation: Module1Ref1ReadActivation,
) -> None:
    assert activation.policy is not None
    assert APPROVED_PURPOSES == ("admin_taxonomy_read", "internal_diagnostics")
    assert set(APPROVED_PURPOSES).isdisjoint(DENIED_PURPOSES)
    assert activation.policy.purpose_allowed("admin_taxonomy_read")
    assert activation.policy.purpose_allowed("internal_diagnostics")
    assert not activation.policy.purpose_allowed("material_write")
    assert not activation.policy.purpose_allowed("unknown")


def test_ref_only_code_is_readable_only_for_approved_purpose_and_never_write_eligible(
    activation: Module1Ref1ReadActivation,
) -> None:
    assert activation.policy is not None
    allowed = activation.policy.eligibility("acoustic_ceiling_panel", purpose="admin_taxonomy_read")
    denied = activation.policy.eligibility("acoustic_ceiling_panel", purpose="matching_candidate")

    assert allowed.recognised_for_legacy_read is False
    assert allowed.recognised_for_ref_read is True
    assert allowed.reason == "ref_only_read_only"
    assert allowed.source == "ref1"
    assert allowed.eligible_for_material_write is False
    assert allowed.eligible_for_catalog_product_write is False
    assert allowed.eligible_for_normalizer_output is False
    assert allowed.eligible_for_matching is False
    assert allowed.eligible_for_moderation_approval is False
    assert denied.recognised_for_ref_read is False
    assert denied.reason == "purpose_denied"


def test_legacy_and_unknown_eligibility_preserve_strict_boundaries(
    activation: Module1Ref1ReadActivation,
) -> None:
    assert activation.policy is not None
    legacy = activation.policy.eligibility("aerated_concrete_block", purpose="admin_taxonomy_read")
    unknown = activation.policy.eligibility("not_a_material_type", purpose="admin_taxonomy_read")

    assert legacy.recognised_for_legacy_read is True
    assert legacy.recognised_for_ref_read is True
    assert legacy.reason == "legacy_behavior_unchanged"
    assert legacy.eligible_for_material_write is True
    assert legacy.eligible_for_catalog_product_write is True
    assert unknown.recognised_for_legacy_read is False
    assert unknown.recognised_for_ref_read is False
    assert unknown.eligible_for_material_write is False
    assert unknown.eligible_for_matching is False
    assert unknown.reason == "unknown_code"


def test_liquid_waterproofing_has_one_ref_parent_and_metadata_only_legacy_paths(
    activation: Module1Ref1ReadActivation,
) -> None:
    assert activation.projection is not None
    matches = [item for item in activation.projection.material_types if item.code == "liquid_waterproofing"]

    assert len(matches) == 1
    assert matches[0].canonical_parent == "waterproofing"
    assert matches[0].read_status == "LEGACY_COMPATIBLE_READ_ONLY"
    metadata = activation.projection.compatibility_metadata["liquid_waterproofing"]
    assert metadata["legacy_parent_paths"] == (
        "primers_chemicals_sealants",
        "waterproofing",
    )
    assert metadata["legacy_paths_metadata_only"] is True
    assert metadata["write_eligible"] is False
    assert activation.policy is not None
    eligibility = activation.policy.eligibility("liquid_waterproofing", purpose="admin_taxonomy_read")
    assert eligibility.source == "legacy"


def test_ref2_ref3_tools_docs_and_business_services_are_not_imported() -> None:
    policy_source = (PROJECT_ROOT / "app/services/module1_ref1_read_policy.py").read_text(encoding="utf-8")
    loader_source = (PROJECT_ROOT / "app/services/module1_ref_runtime_artifacts.py").read_text(encoding="utf-8")
    combined = policy_source + loader_source

    assert "tools.module1_ref_projection" not in combined
    assert "docs/Modules" not in combined
    assert "reference_data" not in combined
    assert "module1_material_normalizer" not in combined
    assert "module1_matching_dedup" not in combined
    assert "module1_moderation_core" not in combined
    assert "module1_export_packages" not in combined
    assert "sqlalchemy" not in policy_source
    assert "app.models" not in policy_source


def test_lm_policy_does_not_activate_ref3_or_unit_conversion_behavior(
    activation: Module1Ref1ReadActivation,
) -> None:
    assert activation.is_valid
    policy_source = (PROJECT_ROOT / "app/services/module1_ref1_read_policy.py").read_text(encoding="utf-8")
    unit_source = (PROJECT_ROOT / "app/services/module1_unit_conversion_registry.py").read_text(encoding="utf-8")

    assert "module1_unit_conversion_registry" not in policy_source
    assert "ref3_activation_allowed" in policy_source
    assert "module1_ref1_read_policy" not in unit_source
