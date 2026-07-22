from __future__ import annotations

import argparse
import subprocess
from collections import Counter
from pathlib import Path
from typing import Iterable

from .portability import (
    PROJECT_ROOT,
    build_portability_approval,
    canonical_content,
    serialize_portability_approval,
    sha256_bytes,
)


TRACKED_ROOTS = (
    "docs/Modules/module1/reference_data",
    "src/modules/module1/runtime_reference",
)
PORTABILITY_DEPENDENCIES: tuple[str, ...] = tuple()


def governed_paths(project_root: Path = PROJECT_ROOT) -> tuple[Path, ...]:
    result = subprocess.run(
        ["git", "ls-files", "--", *TRACKED_ROOTS, *PORTABILITY_DEPENDENCIES],
        cwd=project_root,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    paths = []
    for relative in result.stdout.splitlines():
        normalized = relative.replace("\\", "/")
        if "/approvals/ref-portability-v1-" in normalized:
            continue
        path = project_root / relative
        if path.is_file():
            paths.append(path)
    return tuple(sorted(paths))


def write_portability_approval(
    output_root: Path,
    *,
    project_root: Path = PROJECT_ROOT,
) -> tuple[Path, dict]:
    payload = build_portability_approval(governed_paths(project_root), project_root=project_root)
    target = output_root / str(payload["portability_approval_id"]) / "approval_manifest.json"
    content = serialize_portability_approval(payload)
    if target.exists() and target.read_bytes() != content:
        raise ValueError(f"Immutable portability approval differs: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target, payload


def render_audit_report(payload: dict) -> str:
    records = list(payload["files"])
    kinds = Counter(str(item["canonicalization_kind"]) for item in records)
    raw_dependent = [item for item in records if item["raw_digest_changes_crlf_to_lf"]]
    lines = [
        "# Module №1 REF Artifact Portability Report v1",
        "",
        "## Scope",
        "",
        "Machine-readable inventory is the governed portability approval manifest. This report contains no absolute paths or payload data.",
        "",
        "## Summary",
        "",
        f"- Audited files: {len(records)}.",
        f"- JSON: {kinds.get('json_v1', 0)}.",
        f"- Markdown/text: {kinds.get('text_newline_v1', 0)}.",
        f"- Binary: {kinds.get('raw_binary', 0)}.",
        f"- Raw-byte-dependent before portability approval: {len(raw_dependent)}.",
        f"- Canonically portable after approval: {len(records) - kinds.get('raw_binary', 0)}.",
        "",
        "## Contract",
        "",
        "Raw SHA-256 remains provenance. Cross-platform identity uses canonical content SHA-256. JSON is parsed strictly, rejects BOM, duplicate keys, invalid UTF-8, invalid JSON and NaN/Infinity, sorts object keys, and preserves array order and string values. Markdown/text only normalizes CRLF or CR to LF; spaces and structure remain significant. Binary files remain raw-byte exact.",
        "",
        "A raw mismatch with an equal canonical digest is `canonical_portable_match` and is logged diagnostically. Any semantic mismatch is fail-closed.",
        "",
        "## Audited Files",
        "",
        "| Path | Type | Git blob | Raw SHA-256 | CRLF raw | LF raw | Canonical SHA-256 | BOM | CRLF | Raw EOL dependent | Validator | Approval/startup impact | Status |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---|---|---|",
    ]
    for item in records:
        path = str(item["path"])
        if "/reference_data/" in path:
            validator = "REF source loader/projection validator"
            impact = "build/approval validation; approved mode provenance"
        elif "/approvals/" in path:
            validator = "REF runtime approval validator"
            impact = "mode activation and startup"
        elif "/runtime_reference/" in path:
            validator = "REF runtime artifact validator"
            impact = "mode activation and startup"
        else:
            validator = "REF runtime artifact generator"
            impact = "deterministic generation"
        status = "raw_byte_dependent" if item["raw_digest_changes_crlf_to_lf"] else "portable"
        lines.append(
            "| {path} | {kind} | `{blob}` | `{raw}` | `{crlf}` | `{lf}` | `{canonical}` | {bom} | {has_crlf} | {dependent} | {validator} | {impact} | {status} |".format(
                path=path,
                kind=item["file_type"],
                blob=item["git_blob_identity"],
                raw=item["existing_raw_sha256"],
                crlf=item["crlf_normalized_raw_sha256"],
                lf=item["lf_normalized_raw_sha256"],
                canonical=item["canonical_content_sha256"],
                bom=str(item["has_utf8_bom"]).lower(),
                has_crlf=str(item["has_crlf"]).lower(),
                dependent=str(item["raw_digest_changes_crlf_to_lf"]).lower(),
                validator=validator,
                impact=impact,
                status=status,
            )
        )
    lines.extend(
        [
            "",
            "## Governance",
            "",
            f"- Portability approval: `{payload['portability_approval_id']}`.",
            "- Canonicalization version: `1.0`.",
            "- Runtime defaults, write activation and database state are unchanged.",
            "- REF business content and existing approvals are unchanged.",
            "",
        ]
    )
    return "\n".join(lines)


def write_audit_report(path: Path, payload: dict) -> Path:
    content = render_audit_report(payload).encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build governed REF portability approval")
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--report", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    target, payload = write_portability_approval(args.output_root)
    if args.report:
        write_audit_report(args.report, payload)
    manifest_canonical = canonical_content(target.read_bytes(), "json_v1").canonical_sha256
    print(f"path={target}")
    print(f"raw_sha256={sha256_bytes(target.read_bytes())}")
    print(f"canonical_sha256={manifest_canonical}")
    print(f"files={len(payload['files'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
