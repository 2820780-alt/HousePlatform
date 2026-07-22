from __future__ import annotations

import hashlib
import json
import logging
import subprocess
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUNTIME_REFERENCE_ROOT = PROJECT_ROOT / "src" / "modules" / "module1" / "runtime_reference"
PORTABILITY_APPROVAL_ROOT = RUNTIME_REFERENCE_ROOT / "approvals"
PORTABILITY_APPROVAL_GLOB = "ref-portability-v1-*"
CANONICALIZATION_VERSION = "1.0"
PORTABILITY_APPROVAL_SCHEMA_VERSION = "1.0"
DECISION_NUMBER = "042"

# Filled after deterministic generation of the versioned approval manifest.
EXPECTED_PORTABILITY_MANIFEST_CANONICAL_SHA256 = "cb6e7864a8f2b08d9b771a78f2d68721c0c4ccca0239af6dd5c8967ed6a89f10"

STATUS_RAW_EXACT_MATCH = "raw_exact_match"
STATUS_CANONICAL_PORTABLE_MATCH = "canonical_portable_match"
STATUS_SEMANTIC_MISMATCH = "semantic_mismatch"
STATUS_INVALID_ENCODING = "invalid_encoding"
STATUS_BOM_FORBIDDEN = "bom_forbidden"
STATUS_DUPLICATE_JSON_KEY = "duplicate_json_key"
STATUS_INVALID_JSON = "invalid_json"
STATUS_INVALID_NUMBER = "invalid_number"
STATUS_UNKNOWN_CANONICALIZATION = "unknown_canonicalization"
STATUS_MISSING_FILE = "missing_file"
STATUS_RAW_PROVENANCE_MISMATCH = "raw_provenance_mismatch"

JSON_CANONICALIZATION = "json_v1"
TEXT_CANONICALIZATION = "text_newline_v1"
RAW_BINARY_CANONICALIZATION = "raw_binary"

LOGGER = logging.getLogger(__name__)


class PortabilityValidationError(ValueError):
    def __init__(self, status: str, message: str) -> None:
        super().__init__(message)
        self.status = status


class _DuplicateKeyError(ValueError):
    pass


class _InvalidNumberError(ValueError):
    pass


@dataclass(frozen=True)
class CanonicalContent:
    kind: str
    canonical_bytes: bytes
    canonical_sha256: str


@dataclass(frozen=True)
class PortableDigestResult:
    path: Path
    repository_path: str
    status: str
    accepted: bool
    raw_sha256: str | None
    approved_raw_sha256: str | None
    canonical_sha256: str | None
    expected_canonical_sha256: str | None
    canonicalization_kind: str | None
    diagnostic: str


def sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def canonical_content_bytes(raw: bytes, kind: str) -> bytes:
    if kind == JSON_CANONICALIZATION:
        return _canonical_json_bytes(raw)
    if kind == TEXT_CANONICALIZATION:
        return _canonical_text_bytes(raw)
    if kind == RAW_BINARY_CANONICALIZATION:
        return raw
    raise PortabilityValidationError(
        STATUS_UNKNOWN_CANONICALIZATION,
        f"Unknown canonicalization kind: {kind}",
    )


def canonical_content(raw: bytes, kind: str) -> CanonicalContent:
    content = canonical_content_bytes(raw, kind)
    return CanonicalContent(
        kind=kind,
        canonical_bytes=content,
        canonical_sha256=sha256_bytes(content),
    )


def strict_json_loads(raw: bytes) -> Any:
    canonical = _canonical_json_bytes(raw)
    return json.loads(canonical.decode("utf-8"))


def strict_json_file(path: str | Path) -> Any:
    candidate = Path(path)
    if not candidate.is_file():
        raise PortabilityValidationError(STATUS_MISSING_FILE, f"Missing file: {candidate.name}")
    return strict_json_loads(candidate.read_bytes())


def default_portability_manifest_path() -> Path:
    candidates = sorted(
        path / "approval_manifest.json"
        for path in PORTABILITY_APPROVAL_ROOT.glob(PORTABILITY_APPROVAL_GLOB)
        if (path / "approval_manifest.json").is_file()
    )
    if len(candidates) != 1:
        raise PortabilityValidationError(
            STATUS_RAW_PROVENANCE_MISMATCH,
            "Exactly one governed REF portability approval manifest is required",
        )
    return candidates[0]


def load_portability_manifest(path: str | Path | None = None) -> dict[str, Any]:
    candidate = Path(path) if path is not None else default_portability_manifest_path()
    if path is None:
        return _load_default_portability_manifest(str(candidate.resolve()))
    return _load_portability_manifest(candidate)


@lru_cache(maxsize=1)
def _load_default_portability_manifest(path: str) -> dict[str, Any]:
    return _load_portability_manifest(Path(path))


def _load_portability_manifest(candidate: Path) -> dict[str, Any]:
    with candidate.open("rb") as stream:
        raw = stream.read()
    canonical = canonical_content(raw, JSON_CANONICALIZATION)
    if EXPECTED_PORTABILITY_MANIFEST_CANONICAL_SHA256 == "PENDING":
        raise PortabilityValidationError(
            STATUS_RAW_PROVENANCE_MISMATCH,
            "Portability approval manifest identity is not configured",
        )
    if canonical.canonical_sha256 != EXPECTED_PORTABILITY_MANIFEST_CANONICAL_SHA256:
        raise PortabilityValidationError(
            STATUS_SEMANTIC_MISMATCH,
            "Portability approval manifest canonical digest mismatch",
        )
    payload = strict_json_loads(raw)
    if not isinstance(payload, dict):
        raise PortabilityValidationError(STATUS_INVALID_JSON, "Portability manifest must be an object")
    checks = (
        payload.get("approval_schema_version") == PORTABILITY_APPROVAL_SCHEMA_VERSION,
        payload.get("canonicalization_version") == CANONICALIZATION_VERSION,
        str(payload.get("decision_number")) == DECISION_NUMBER,
        payload.get("db_mutation_allowed") is False,
        payload.get("write_activation_allowed") is False,
        payload.get("automatic_replacement_allowed") is False,
        payload.get("quantity_execution_allowed") is False,
        payload.get("generated_deterministically") is True,
    )
    if not all(checks):
        raise PortabilityValidationError(
            STATUS_SEMANTIC_MISMATCH,
            "Portability approval governance contract mismatch",
        )
    return payload


def validate_portable_file(
    path: str | Path,
    *,
    expected_raw_sha256: str | None = None,
    manifest_path: str | Path | None = None,
) -> PortableDigestResult:
    candidate = Path(path)
    repository_path = repository_relative_path(candidate)
    if not candidate.is_file():
        return _result(candidate, repository_path, STATUS_MISSING_FILE, False, diagnostic="file is missing")

    try:
        manifest = load_portability_manifest(manifest_path)
    except PortabilityValidationError as exc:
        return _result(candidate, repository_path, exc.status, False, diagnostic=str(exc))

    records = {
        str(item.get("path")): item
        for item in manifest.get("files", [])
        if isinstance(item, dict)
    }
    record = records.get(repository_path)
    if record is None and expected_raw_sha256 is not None:
        provenance_matches = [
            item
            for item in records.values()
            if item.get("existing_raw_sha256") == expected_raw_sha256
        ]
        if len(provenance_matches) == 1:
            record = provenance_matches[0]
    raw = candidate.read_bytes()
    raw_sha256 = sha256_bytes(raw)
    if record is None:
        if expected_raw_sha256 is not None and raw_sha256 == expected_raw_sha256:
            return _result(
                candidate,
                repository_path,
                STATUS_RAW_EXACT_MATCH,
                True,
                raw_sha256=raw_sha256,
                approved_raw_sha256=expected_raw_sha256,
                diagnostic="exact raw match outside the governed repository path",
            )
        return _result(
            candidate,
            repository_path,
            STATUS_RAW_PROVENANCE_MISMATCH,
            False,
            raw_sha256=raw_sha256,
            diagnostic="file is absent from the governed portability manifest",
        )

    approved_raw = str(record.get("existing_raw_sha256") or "")
    expected_canonical = str(record.get("canonical_content_sha256") or "")
    kind = str(record.get("canonicalization_kind") or "")
    if expected_raw_sha256 is not None and expected_raw_sha256 != approved_raw:
        return _result(
            candidate,
            repository_path,
            STATUS_RAW_PROVENANCE_MISMATCH,
            False,
            raw_sha256=raw_sha256,
            approved_raw_sha256=approved_raw,
            expected_canonical_sha256=expected_canonical,
            canonicalization_kind=kind,
            diagnostic="caller raw provenance differs from the governed manifest",
        )

    try:
        canonical = canonical_content(raw, kind)
    except PortabilityValidationError as exc:
        return _result(
            candidate,
            repository_path,
            exc.status,
            False,
            raw_sha256=raw_sha256,
            approved_raw_sha256=approved_raw,
            expected_canonical_sha256=expected_canonical,
            canonicalization_kind=kind,
            diagnostic=str(exc),
        )

    if canonical.canonical_sha256 != expected_canonical:
        status = (
            STATUS_RAW_PROVENANCE_MISMATCH
            if kind == RAW_BINARY_CANONICALIZATION
            else STATUS_SEMANTIC_MISMATCH
        )
        return _result(
            candidate,
            repository_path,
            status,
            False,
            raw_sha256=raw_sha256,
            approved_raw_sha256=approved_raw,
            canonical_sha256=canonical.canonical_sha256,
            expected_canonical_sha256=expected_canonical,
            canonicalization_kind=kind,
            diagnostic="canonical content digest mismatch",
        )

    status = STATUS_RAW_EXACT_MATCH if raw_sha256 == approved_raw else STATUS_CANONICAL_PORTABLE_MATCH
    if status == STATUS_CANONICAL_PORTABLE_MATCH:
        LOGGER.info("REF portability diagnostic: %s path=%s", status, repository_path)
    return _result(
        candidate,
        repository_path,
        status,
        True,
        raw_sha256=raw_sha256,
        approved_raw_sha256=approved_raw,
        canonical_sha256=canonical.canonical_sha256,
        expected_canonical_sha256=expected_canonical,
        canonicalization_kind=kind,
        diagnostic="raw provenance exact" if status == STATUS_RAW_EXACT_MATCH else "raw bytes differ; canonical content approved",
    )


def portable_identity_sha256(
    path: str | Path,
    *,
    expected_raw_sha256: str | None = None,
    manifest_path: str | Path | None = None,
) -> str:
    result = validate_portable_file(
        path,
        expected_raw_sha256=expected_raw_sha256,
        manifest_path=manifest_path,
    )
    if not result.accepted or not result.approved_raw_sha256:
        raise PortabilityValidationError(result.status, result.diagnostic)
    return result.approved_raw_sha256


def portable_identity_or_raw(path: str | Path) -> str:
    candidate = Path(path)
    result = validate_portable_file(candidate)
    if result.accepted and result.approved_raw_sha256:
        return result.approved_raw_sha256
    if candidate.is_file():
        return sha256_bytes(candidate.read_bytes())
    raise PortabilityValidationError(STATUS_MISSING_FILE, f"Missing file: {candidate.name}")


def repository_relative_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        pass

    normalized_parts = tuple(part.casefold() for part in resolved.parts)
    anchors = (
        ("docs", "modules", "module1", "reference" + "_data"),
        ("src", "modules", "module1", "runtime_reference"),
        ("src", "modules", "module1", "seeds"),
        ("app", "services"),
        ("tools", "module1_ref_" + "projection"),
    )
    for anchor in anchors:
        width = len(anchor)
        for index in range(len(normalized_parts) - width + 1):
            if normalized_parts[index : index + width] == anchor:
                return Path(*resolved.parts[index:]).as_posix()
    return resolved.as_posix()


def canonicalization_kind_for_path(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        return JSON_CANONICALIZATION
    if suffix in {".md", ".txt", ".py"}:
        return TEXT_CANONICALIZATION
    return RAW_BINARY_CANONICALIZATION


def build_portability_approval(
    paths: Iterable[Path],
    *,
    project_root: Path = PROJECT_ROOT,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    for path in sorted((Path(item) for item in paths), key=lambda item: repository_relative_path(item)):
        raw = path.read_bytes()
        kind = canonicalization_kind_for_path(path)
        canonical = canonical_content(raw, kind)
        lf_raw, crlf_raw = _line_materializations(raw, kind)
        records.append(
            {
                "allowed_transformations": ["crlf_to_lf", "lf_to_crlf", "cr_to_lf"] if kind != RAW_BINARY_CANONICALIZATION else [],
                "canonical_content_sha256": canonical.canonical_sha256,
                "canonicalization_kind": kind,
                "crlf_normalized_raw_sha256": sha256_bytes(crlf_raw),
                "existing_raw_sha256": sha256_bytes(raw),
                "file_type": _file_type(path),
                "forbidden_transformations": ["semantic_content_change", "array_reorder", "string_whitespace_change"],
                "git_blob_identity": _git_blob_identity(path, project_root),
                "has_crlf": b"\r\n" in raw,
                "has_utf8_bom": raw.startswith(b"\xef\xbb\xbf"),
                "lf_normalized_raw_sha256": sha256_bytes(lf_raw),
                "path": repository_relative_path(path),
                "raw_digest_changes_crlf_to_lf": sha256_bytes(raw) != sha256_bytes(lf_raw),
            }
        )

    bundle = sha256_bytes(_canonical_payload_bytes(records))
    approval_id = f"ref-portability-v1-{bundle[:12]}"
    runtime_ids = sorted(
        path.name
        for path in (project_root / "src" / "modules" / "module1" / "runtime_reference").iterdir()
        if path.is_dir() and path.name.startswith("ref") and path.name != "approvals"
    )
    return {
        "allowed_transformations": ["json_object_key_reorder", "json_token_whitespace", "text_newline_normalization"],
        "approval_files": sorted(record["path"] for record in records if "/approvals/" in record["path"]),
        "approval_schema_version": PORTABILITY_APPROVAL_SCHEMA_VERSION,
        "automatic_replacement_allowed": False,
        "canonical_portable_match_policy": "accept_with_diagnostic_when_canonical_digest_matches",
        "canonicalization_version": CANONICALIZATION_VERSION,
        "db_mutation_allowed": False,
        "decision_number": DECISION_NUMBER,
        "files": records,
        "forbidden_transformations": ["semantic_content_change", "array_reorder", "business_reference_change"],
        "generated_deterministically": True,
        "portability_approval_id": approval_id,
        "quantity_execution_allowed": False,
        "raw_exact_match_policy": "accept_after_strict_content_validation",
        "rollback_policy": "mode_switch_and_restart",
        "runtime_artifact_ids": runtime_ids,
        "semantic_mismatch_policy": "fail_closed",
        "source_file_list": sorted(record["path"] for record in records if "/reference" + "_data/" in record["path"]),
        "write_activation_allowed": False,
    }


def serialize_portability_approval(payload: Mapping[str, Any]) -> bytes:
    return _canonical_payload_bytes(payload)


def _canonical_json_bytes(raw: bytes) -> bytes:
    text = _decode_text(raw)
    decimal_payload = _parse_json(text, parse_decimals=True)
    regular_payload = _parse_json(text, parse_decimals=False)
    try:
        serialized = (
            json.dumps(
                regular_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise PortabilityValidationError(STATUS_INVALID_NUMBER, "JSON contains an invalid number") from exc
    reparsed_decimal = _parse_json(serialized.decode("utf-8"), parse_decimals=True)
    if decimal_payload != reparsed_decimal:
        raise PortabilityValidationError(
            STATUS_INVALID_NUMBER,
            "JSON number cannot be canonicalized without precision loss",
        )
    return serialized


def _canonical_text_bytes(raw: bytes) -> bytes:
    text = _decode_text(raw)
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def _decode_text(raw: bytes) -> str:
    if raw.startswith(b"\xef\xbb\xbf"):
        raise PortabilityValidationError(STATUS_BOM_FORBIDDEN, "UTF-8 BOM is forbidden")
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise PortabilityValidationError(STATUS_INVALID_ENCODING, "Invalid UTF-8 encoding") from exc


def _parse_json(text: str, *, parse_decimals: bool) -> Any:
    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateKeyError(key)
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise _InvalidNumberError(value)

    try:
        return json.loads(
            text,
            object_pairs_hook=reject_duplicate_pairs,
            parse_float=Decimal if parse_decimals else float,
            parse_int=int,
            parse_constant=reject_constant,
        )
    except _DuplicateKeyError as exc:
        raise PortabilityValidationError(STATUS_DUPLICATE_JSON_KEY, "Duplicate JSON object key") from exc
    except _InvalidNumberError as exc:
        raise PortabilityValidationError(STATUS_INVALID_NUMBER, "NaN and Infinity are forbidden") from exc
    except json.JSONDecodeError as exc:
        raise PortabilityValidationError(STATUS_INVALID_JSON, "Invalid JSON") from exc


def _canonical_payload_bytes(payload: Any) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _line_materializations(raw: bytes, kind: str) -> tuple[bytes, bytes]:
    if kind == RAW_BINARY_CANONICALIZATION:
        return raw, raw
    text = _decode_text(raw).replace("\r\n", "\n").replace("\r", "\n")
    return text.encode("utf-8"), text.replace("\n", "\r\n").encode("utf-8")


def _git_blob_identity(path: Path, project_root: Path) -> str:
    relative = path.resolve().relative_to(project_root.resolve()).as_posix()
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", relative],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    line = result.stdout.strip()
    if not line:
        return "UNTRACKED"
    return line.split()[1]


def _file_type(path: Path) -> str:
    suffix = path.suffix.casefold()
    if suffix == ".json":
        return "JSON"
    if suffix == ".md":
        return "Markdown"
    if suffix in {".txt", ".py"}:
        return "text"
    return "binary"


def _result(
    path: Path,
    repository_path: str,
    status: str,
    accepted: bool,
    *,
    raw_sha256: str | None = None,
    approved_raw_sha256: str | None = None,
    canonical_sha256: str | None = None,
    expected_canonical_sha256: str | None = None,
    canonicalization_kind: str | None = None,
    diagnostic: str,
) -> PortableDigestResult:
    return PortableDigestResult(
        path=path,
        repository_path=repository_path,
        status=status,
        accepted=accepted,
        raw_sha256=raw_sha256,
        approved_raw_sha256=approved_raw_sha256,
        canonical_sha256=canonical_sha256,
        expected_canonical_sha256=expected_canonical_sha256,
        canonicalization_kind=canonicalization_kind,
        diagnostic=diagnostic,
    )
