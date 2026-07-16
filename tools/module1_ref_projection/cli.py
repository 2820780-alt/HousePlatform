from __future__ import annotations

import argparse
import json
from pathlib import Path

from .validator import ProjectionValidator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inactive Module 1 REF projection foundation")
    parser.add_argument("--reference-root", required=True, help="Directory with REF source packages")
    parser.add_argument("--output-dir", required=True, help="Directory for generated foundation outputs")
    return parser


def run(reference_root: str | Path, output_dir: str | Path) -> dict[str, object]:
    summary = ProjectionValidator(reference_root).validate()
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "foundation_summary.json"
    payload = {
        "tool": "module1_ref_projection",
        "status": "PASS" if summary.blocker_count == 0 else "BLOCKED",
        "summary": summary.as_dict(),
    }
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(args.reference_root, args.output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
