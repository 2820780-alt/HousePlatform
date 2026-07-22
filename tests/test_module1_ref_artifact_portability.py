from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from app.services.module1_ref_artifact_portability import (
    JSON_CANONICALIZATION,
    STATUS_BOM_FORBIDDEN,
    STATUS_CANONICAL_PORTABLE_MATCH,
    STATUS_DUPLICATE_JSON_KEY,
    STATUS_INVALID_ENCODING,
    STATUS_INVALID_JSON,
    STATUS_INVALID_NUMBER,
    STATUS_RAW_EXACT_MATCH,
    STATUS_SEMANTIC_MISMATCH,
    STATUS_UNKNOWN_CANONICALIZATION,
    PortabilityValidationError,
    canonical_content_bytes,
    load_portability_manifest,
    validate_portable_file,
)
from app.services.module1_ref_runtime_artifacts import validate_module1_ref_runtime
from app.services.module1_ref4_normalization_policy import validate_module1_ref45_runtime
from app.services.module1_ref6_work_material_policy import validate_module1_ref6_runtime
from tools.module1_ref_projection.ref45 import build_ref45_runtime_artifacts
from tools.module1_ref_projection.ref6 import build_ref6_runtime_artifacts
from tools.module1_ref_projection.runtime_artifacts import build_runtime_artifact_package


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data"
RUNTIME_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
MAIN_ARTIFACT_ID = "ref-runtime-v1-122079b1c558fefc"
REF1_APPROVAL_ID = "ref1-read-v1-1a15fed6ebdd"
REF2_APPROVAL_ID = "ref2-read-v1-1a15fed6ebdd"
REF3_APPROVAL_ID = "ref3-read-v1-1a15fed6ebdd"
REF45_ARTIFACT_ID = "ref45-runtime-v1-5fe5e067d0dd"
REF45_APPROVAL_ID = "ref45-activation-v1-5fe5e067d0dd"
REF6_ARTIFACT_ID = "ref6-runtime-v1-2256595bd388"
REF6_APPROVAL_ID = "ref6-activation-v1-2256595bd388"

JSON_SOURCE = REFERENCE_ROOT / "ATOM_REF1_Material_Taxonomy_v2_PRELIMINARY_APPROVED.json"
MARKDOWN_SOURCE = REFERENCE_ROOT / "ATOM_REF_Data_Correction_Governance_v1.md"


def _lf_bytes(raw: bytes) -> bytes:
    return raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")


def _crlf_bytes(raw: bytes) -> bytes:
    return _lf_bytes(raw).replace(b"\n", b"\r\n")


def _copy_as_repository_path(tmp_path: Path, source: Path, content: bytes) -> Path:
    relative = source.relative_to(PROJECT_ROOT)
    target = tmp_path / "project" / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def _json_mutation(payload: dict, *, key: str, value: object) -> bytes:
    changed = dict(payload)
    changed[key] = value
    return (json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def _copy_runtime_tree(tmp_path: Path, *, lf: bool) -> Path:
    target = tmp_path / "project" / "src" / "modules" / "module1" / "runtime_reference"
    shutil.copytree(RUNTIME_ROOT, target)
    if lf:
        for path in target.rglob("*"):
            if path.is_file() and path.suffix.casefold() in {".json", ".md", ".txt"}:
                path.write_bytes(_lf_bytes(path.read_bytes()))
    return target


def _validate_mode_matrix(runtime_root: Path) -> tuple[int, int]:
    scenarios = (
        ("legacy", "legacy", "legacy"),
        ("artifact_validation", "legacy", "legacy"),
        ("dual_read", "legacy", "legacy"),
        ("ref1_read", "approved", "legacy"),
        ("ref2_read", "approved", "legacy"),
        ("ref3_read", "approved", "approved"),
    )
    approvals = runtime_root / "approvals"
    for main_mode, ref45_mode, ref6_mode in scenarios:
        main = validate_module1_ref_runtime(
            main_mode,
            artifact_dir=runtime_root / MAIN_ARTIFACT_ID,
            allowed_root=runtime_root,
            approval_dir=approvals / REF1_APPROVAL_ID,
            ref2_approval_dir=approvals / REF2_APPROVAL_ID,
            ref3_approval_dir=approvals / REF3_APPROVAL_ID,
            approval_allowed_root=approvals,
        )
        assert main.is_valid, (main_mode, main.issues)
        ref45 = validate_module1_ref45_runtime(
            ref45_mode,
            artifact_dir=runtime_root / REF45_ARTIFACT_ID,
            approval_path=approvals / REF45_APPROVAL_ID / "approval_manifest.json",
            allowed_root=runtime_root,
        )
        assert ref45.is_valid, (ref45_mode, ref45.issues)
        ref6 = validate_module1_ref6_runtime(
            ref6_mode,
            artifact_dir=runtime_root / REF6_ARTIFACT_ID,
            approval_path=approvals / REF6_APPROVAL_ID / "approval_manifest.json",
            allowed_root=runtime_root,
        )
        assert ref6.is_valid, (ref6_mode, ref6.issues)

    rollback = (
        ("ref3_read", "approved", "approved"),
        ("ref2_read", "approved", "legacy"),
        ("ref1_read", "legacy", "legacy"),
        ("legacy", "legacy", "legacy"),
    )
    for main_mode, ref45_mode, ref6_mode in rollback:
        main = validate_module1_ref_runtime(
            main_mode,
            artifact_dir=runtime_root / MAIN_ARTIFACT_ID,
            allowed_root=runtime_root,
            approval_dir=approvals / REF1_APPROVAL_ID,
            ref2_approval_dir=approvals / REF2_APPROVAL_ID,
            ref3_approval_dir=approvals / REF3_APPROVAL_ID,
            approval_allowed_root=approvals,
        )
        assert main.is_valid
        assert validate_module1_ref45_runtime(
            ref45_mode,
            artifact_dir=runtime_root / REF45_ARTIFACT_ID,
            approval_path=approvals / REF45_APPROVAL_ID / "approval_manifest.json",
            allowed_root=runtime_root,
        ).is_valid
        assert validate_module1_ref6_runtime(
            ref6_mode,
            artifact_dir=runtime_root / REF6_ARTIFACT_ID,
            approval_path=approvals / REF6_APPROVAL_ID / "approval_manifest.json",
            allowed_root=runtime_root,
        ).is_valid
    return len(scenarios), len(rollback)


def test_portability_manifest_is_governed_and_complete() -> None:
    manifest = load_portability_manifest()

    assert manifest["decision_number"] == "042"
    assert manifest["canonicalization_version"] == "1.0"
    assert manifest["generated_deterministically"] is True
    assert manifest["db_mutation_allowed"] is False
    assert manifest["write_activation_allowed"] is False
    assert len(manifest["files"]) == 49
    assert all(not item["has_utf8_bom"] for item in manifest["files"])


def test_original_crlf_and_lf_materializations_are_portable(tmp_path: Path) -> None:
    raw = JSON_SOURCE.read_bytes()
    original = validate_portable_file(JSON_SOURCE)
    crlf = validate_portable_file(_copy_as_repository_path(tmp_path / "crlf", JSON_SOURCE, _crlf_bytes(raw)))
    lf = validate_portable_file(_copy_as_repository_path(tmp_path / "lf", JSON_SOURCE, _lf_bytes(raw)))

    assert original.status == STATUS_RAW_EXACT_MATCH
    assert original.accepted
    assert crlf.accepted and crlf.status in {STATUS_RAW_EXACT_MATCH, STATUS_CANONICAL_PORTABLE_MATCH}
    assert lf.accepted and lf.status in {STATUS_RAW_EXACT_MATCH, STATUS_CANONICAL_PORTABLE_MATCH}
    assert original.canonical_sha256 == crlf.canonical_sha256 == lf.canonical_sha256


def test_json_key_order_and_token_whitespace_are_non_semantic(tmp_path: Path) -> None:
    payload = json.loads(JSON_SOURCE.read_text(encoding="utf-8"))
    reordered = dict(reversed(tuple(payload.items())))
    compact = json.dumps(reordered, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    pretty = (json.dumps(reordered, ensure_ascii=False, indent=4) + "\n").encode("utf-8")

    for index, content in enumerate((compact, pretty)):
        result = validate_portable_file(_copy_as_repository_path(tmp_path / str(index), JSON_SOURCE, content))
        assert result.accepted
        assert result.status == STATUS_CANONICAL_PORTABLE_MATCH


@pytest.mark.parametrize("mutation", ("string_space", "field_value", "array_order"))
def test_json_semantic_mutations_fail_closed(tmp_path: Path, mutation: str) -> None:
    payload = json.loads(JSON_SOURCE.read_text(encoding="utf-8"))
    if mutation == "string_space":
        content = _json_mutation(payload, key="status", value=str(payload["status"]) + " ")
    elif mutation == "field_value":
        content = _json_mutation(payload, key="version", value="semantic-change")
    else:
        changed = dict(payload)
        changed["groups"] = list(reversed(changed["groups"]))
        content = (json.dumps(changed, ensure_ascii=False, indent=2) + "\n").encode("utf-8")

    result = validate_portable_file(_copy_as_repository_path(tmp_path, JSON_SOURCE, content))
    assert not result.accepted
    assert result.status == STATUS_SEMANTIC_MISMATCH


@pytest.mark.parametrize(
    ("content", "status"),
    (
        (b'{"package_id":"duplicate",' + JSON_SOURCE.read_bytes().lstrip()[1:], STATUS_DUPLICATE_JSON_KEY),
        (b"\xef\xbb\xbf" + JSON_SOURCE.read_bytes(), STATUS_BOM_FORBIDDEN),
        (b"\xff\xfe{}", STATUS_INVALID_ENCODING),
        (b'{"broken":', STATUS_INVALID_JSON),
        (b'{"invalid":NaN}', STATUS_INVALID_NUMBER),
        (b'{"invalid":Infinity}', STATUS_INVALID_NUMBER),
    ),
    ids=("duplicate_key", "bom", "invalid_utf8", "invalid_json", "nan", "infinity"),
)
def test_invalid_json_forms_fail_closed(tmp_path: Path, content: bytes, status: str) -> None:
    result = validate_portable_file(_copy_as_repository_path(tmp_path, JSON_SOURCE, content))
    assert not result.accepted
    assert result.status == status


def test_markdown_newlines_are_portable_but_text_changes_are_not(tmp_path: Path) -> None:
    raw = MARKDOWN_SOURCE.read_bytes()
    lf = validate_portable_file(_copy_as_repository_path(tmp_path / "lf", MARKDOWN_SOURCE, _lf_bytes(raw)))
    crlf = validate_portable_file(_copy_as_repository_path(tmp_path / "crlf", MARKDOWN_SOURCE, _crlf_bytes(raw)))
    changed = validate_portable_file(_copy_as_repository_path(tmp_path / "changed", MARKDOWN_SOURCE, raw + b"changed\n"))
    trailing = validate_portable_file(_copy_as_repository_path(tmp_path / "trailing", MARKDOWN_SOURCE, raw + b" \n"))

    assert lf.accepted and crlf.accepted
    assert changed.status == STATUS_SEMANTIC_MISMATCH and not changed.accepted
    assert trailing.status == STATUS_SEMANTIC_MISMATCH and not trailing.accepted


def test_unknown_canonicalization_fails_closed() -> None:
    with pytest.raises(PortabilityValidationError) as exc_info:
        canonical_content_bytes(b"{}", "unknown_v99")
    assert exc_info.value.status == STATUS_UNKNOWN_CANONICALIZATION


def test_original_and_lf_mode_matrices_and_rollbacks(tmp_path: Path) -> None:
    original_root = _copy_runtime_tree(tmp_path / "original", lf=False)
    lf_root = _copy_runtime_tree(tmp_path / "lf", lf=True)

    assert _validate_mode_matrix(original_root) == (6, 4)
    assert _validate_mode_matrix(lf_root) == (6, 4)
    lf_manifest = validate_portable_file(lf_root / MAIN_ARTIFACT_ID / "manifest.json")
    assert lf_manifest.accepted
    assert lf_manifest.status in {STATUS_RAW_EXACT_MATCH, STATUS_CANONICAL_PORTABLE_MATCH}


def test_runtime_artifacts_are_identical_from_original_and_lf_sources(tmp_path: Path) -> None:
    lf_reference = tmp_path / "project" / "docs" / "Modules" / "module1" / "reference_data"
    shutil.copytree(REFERENCE_ROOT, lf_reference)
    for path in lf_reference.rglob("*"):
        if path.is_file() and path.suffix.casefold() in {".json", ".md", ".txt"}:
            path.write_bytes(_lf_bytes(path.read_bytes()))

    original_main = build_runtime_artifact_package(REFERENCE_ROOT, tmp_path / "main-original")
    lf_main = build_runtime_artifact_package(lf_reference, tmp_path / "main-lf")
    assert original_main.artifact_set_id == lf_main.artifact_set_id
    assert {
        path.name: path.read_bytes() for path in original_main.output_dir.iterdir()
    } == {
        path.name: path.read_bytes() for path in lf_main.output_dir.iterdir()
    }

    original_45 = build_ref45_runtime_artifacts(REFERENCE_ROOT, tmp_path / "ref45-original")
    lf_45 = build_ref45_runtime_artifacts(lf_reference, tmp_path / "ref45-lf")
    assert original_45.artifact_set_id == lf_45.artifact_set_id
    assert {
        path.name: path.read_bytes() for path in original_45.output_dir.iterdir()
    } == {
        path.name: path.read_bytes() for path in lf_45.output_dir.iterdir()
    }

    original_6 = build_ref6_runtime_artifacts(REFERENCE_ROOT, tmp_path / "ref6-original")
    lf_6 = build_ref6_runtime_artifacts(lf_reference, tmp_path / "ref6-lf")
    assert original_6.artifact_dir.name == lf_6.artifact_dir.name
    assert {
        path.name: path.read_bytes() for path in original_6.artifact_dir.iterdir()
    } == {
        path.name: path.read_bytes() for path in lf_6.artifact_dir.iterdir()
    }
