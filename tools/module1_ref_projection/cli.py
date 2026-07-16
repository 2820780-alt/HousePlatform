from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .combined import write_combined_projection_outputs
from .ref1 import DEFAULT_RUNTIME_TAXONOMY_PATH, write_ref1_projection_outputs
from .ref2 import write_ref2_projection_outputs
from .ref3_extended import DEFAULT_WORK_CATALOG_PATH, write_ref3_extended_projection_outputs
from .ref3_units import DEFAULT_RUNTIME_UNIT_SERVICE_PATH, write_ref3_unit_projection_outputs
from .validator import ProjectionValidator

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROTECTED_OUTPUT_DIRS = (
    PROJECT_ROOT / "app",
    PROJECT_ROOT / "src",
    PROJECT_ROOT / "migrations",
    PROJECT_ROOT / "docs" / "Modules" / "module1" / "reference_data",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inactive Module 1 REF projection foundation")
    parser.add_argument("--reference-root", required=True, help="Directory with REF source packages")
    parser.add_argument("--output-dir", required=True, help="Directory for generated foundation outputs")
    parser.add_argument("--include-ref1", action="store_true", help="Generate inactive REF-1 taxonomy projection outputs")
    parser.add_argument("--include-ref2", action="store_true", help="Generate inactive REF-2 characteristic projection outputs")
    parser.add_argument("--include-ref3-units", action="store_true", help="Generate inactive REF-3 unit projection outputs")
    parser.add_argument("--include-ref3-extended", action="store_true", help="Generate inactive REF-3 extended rule projection outputs")
    parser.add_argument("--include-combined", action="store_true", help="Generate combined inactive REF projection validation outputs")
    parser.add_argument(
        "--runtime-taxonomy-path",
        default=str(DEFAULT_RUNTIME_TAXONOMY_PATH),
        help="Runtime taxonomy seed used for read-only comparison",
    )
    parser.add_argument(
        "--runtime-unit-service-path",
        default=str(DEFAULT_RUNTIME_UNIT_SERVICE_PATH),
        help="Runtime unit conversion service used for read-only comparison",
    )
    parser.add_argument(
        "--work-catalog-path",
        default=str(DEFAULT_WORK_CATALOG_PATH),
        help="Work catalog seed used for read-only mapping guard",
    )
    return parser


def run(
    reference_root: str | Path,
    output_dir: str | Path,
    *,
    include_ref1: bool = False,
    include_ref2: bool = False,
    include_ref3_units: bool = False,
    include_ref3_extended: bool = False,
    include_combined: bool = False,
    runtime_taxonomy_path: str | Path = DEFAULT_RUNTIME_TAXONOMY_PATH,
    runtime_unit_service_path: str | Path = DEFAULT_RUNTIME_UNIT_SERVICE_PATH,
    work_catalog_path: str | Path = DEFAULT_WORK_CATALOG_PATH,
) -> dict[str, Any]:
    summary = ProjectionValidator(reference_root).validate()
    destination = _validated_output_dir(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    output_path = destination / "foundation_summary.json"
    payload: dict[str, Any] = {
        "tool": "module1_ref_projection",
        "status": "PASS" if summary.blocker_count == 0 else "BLOCKED",
        "summary": summary.as_dict(),
    }
    if include_ref1:
        ref1_result = write_ref1_projection_outputs(reference_root, destination, runtime_taxonomy_path)
        payload["ref1"] = ref1_result.summary_dict()
    if include_ref2:
        ref2_result = write_ref2_projection_outputs(reference_root, destination, runtime_taxonomy_path)
        payload["ref2"] = ref2_result.summary_dict()
    if include_ref3_units:
        ref3_result = write_ref3_unit_projection_outputs(reference_root, destination, runtime_taxonomy_path, runtime_unit_service_path)
        payload["ref3_units"] = ref3_result.summary_dict()
    if include_ref3_extended:
        ref3_extended_result = write_ref3_extended_projection_outputs(reference_root, destination, work_catalog_path)
        payload["ref3_extended"] = ref3_extended_result.summary_dict()
    if include_combined:
        combined_result = write_combined_projection_outputs(
            reference_root,
            destination,
            runtime_taxonomy_path=runtime_taxonomy_path,
            runtime_unit_service_path=runtime_unit_service_path,
            work_catalog_path=work_catalog_path,
        )
        payload["combined"] = combined_result.summary_dict()
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return payload


def _validated_output_dir(output_dir: str | Path) -> Path:
    destination = Path(output_dir)
    resolved = destination.resolve()
    for protected in PROTECTED_OUTPUT_DIRS:
        protected_resolved = protected.resolve()
        if resolved == protected_resolved or protected_resolved in resolved.parents:
            raise ValueError(f"Output directory is inside protected source directory: {protected}")
    return destination


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        run(
            args.reference_root,
            args.output_dir,
            include_ref1=args.include_ref1,
            include_ref2=args.include_ref2,
            include_ref3_units=args.include_ref3_units,
            include_ref3_extended=args.include_ref3_extended,
            include_combined=args.include_combined,
            runtime_taxonomy_path=args.runtime_taxonomy_path,
            runtime_unit_service_path=args.runtime_unit_service_path,
            work_catalog_path=args.work_catalog_path,
        )
    except ValueError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
