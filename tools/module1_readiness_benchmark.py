from __future__ import annotations

from collections import Counter
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
import json
import logging
from pathlib import Path
import statistics
import subprocess
import sys
from types import SimpleNamespace
import time
import tracemalloc
from typing import Any, Iterator

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.api.deps import get_current_user
from app.config import settings
from app.database import engine
from app.main import app
from app.models.enums import UserRole
from app.services.module1_material_normalizer import build_normalization_report
from app.services.module1_raw_ingestion_pipeline import Module1RawIngestionItem
from app.services.module1_ref4_normalization_policy import (
    clear_module1_ref45_runtime_cache,
    require_module1_ref45_runtime,
    resolve_ref4_alias,
)
from app.services.module1_ref6_work_material_policy import (
    clear_module1_ref6_runtime_cache,
    require_module1_ref6_runtime,
    resolve_work_material_hints,
)
from app.services.module1_ref_runtime_artifacts import validate_module1_ref_runtime


VIEW_PATHS = (
    "/api/v1/admin/material-hub/view",
    "/api/v1/admin/material-hub/view/materials",
    "/api/v1/admin/material-hub/view/documents",
    "/api/v1/admin/material-hub/view/work-costs",
)


def _milliseconds(started: float) -> float:
    return round((time.perf_counter() - started) * 1000, 3)


def _median_milliseconds(operation: Any, repeats: int) -> float:
    samples: list[float] = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append(_milliseconds(started))
    return round(statistics.median(samples), 3)


@contextmanager
def _setting(name: str, value: str) -> Iterator[None]:
    original = getattr(settings, name)
    setattr(settings, name, value)
    try:
        yield
    finally:
        setattr(settings, name, original)


def _raw_item(index: int) -> Module1RawIngestionItem:
    bucket = index % 10
    price = None if bucket in {6, 7} else Decimal("12500.00")
    unit = "unsupported_fixture_unit" if bucket == 9 else "м3"
    if bucket == 8:
        return Module1RawIngestionItem(
            legacy_source="raw_payload",
            source_code="BAUCENTER",
            source_url=f"https://fixture.atom.test/ambiguous/{(index // 10) % 10}",
            raw_title="ГКЛ 2500x1200x12.5 мм",
            raw_category="gypsum board",
            raw_price=Decimal("390.00"),
            raw_unit="sheet",
            raw_payload={"external_id": f"ambiguous-{(index // 10) % 10}"},
        )
    return Module1RawIngestionItem(
        legacy_source="raw_payload",
        source_code="BAUCENTER",
        source_type="supplier_site",
        source_url="https://fixture.atom.test/products/gas-block-001",
        raw_title="Газоблок Bonolit D500 B2.5 600x250x200 мм",
        raw_category="gas block",
        raw_price=price,
        raw_unit=unit,
        raw_characteristics={
            "length_mm": 600,
            "width_mm": 250,
            "height_mm": 200,
            "density_class": "D500",
            "strength_class": "B2.5",
            "frost_resistance": "F35",
            "pieces_per_m3": "33.33",
        },
        raw_supplier="ATOM Fixture Supplier",
        raw_manufacturer="Bonolit",
        region="Краснодарский край",
        observed_at=datetime(2026, 7, 21, 12, 0, tzinfo=UTC),
        raw_payload={"external_id": "atom-module1-readiness-product-v1"},
    )


def _measure_ref_runtime() -> dict[str, Any]:
    cold: dict[str, float] = {}
    for mode in (
        "legacy",
        "artifact_validation",
        "dual_read",
        "ref1_read",
        "ref2_read",
        "ref3_read",
    ):
        started = time.perf_counter()
        validate_module1_ref_runtime(mode)
        cold[f"main_{mode}_ms"] = _milliseconds(started)

    clear_module1_ref45_runtime_cache()
    started = time.perf_counter()
    require_module1_ref45_runtime("approved")
    cold["ref45_approved_ms"] = _milliseconds(started)
    clear_module1_ref6_runtime_cache()
    started = time.perf_counter()
    require_module1_ref6_runtime("approved")
    cold["ref6_approved_ms"] = _milliseconds(started)

    cached = {
        "ref45_alias_median_ms": _median_milliseconds(
            lambda: resolve_ref4_alias("газоблок", mode="approved"), 100
        ),
        "ref6_hint_median_ms": _median_milliseconds(
            lambda: resolve_work_material_hints(
                "earthworks_ustroystvo_peschanoy_podushki", mode="approved"
            ),
            100,
        ),
    }
    return {"cold": cold, "cached": cached}


def _measure_memory() -> dict[str, Any]:
    clear_module1_ref45_runtime_cache()
    clear_module1_ref6_runtime_cache()
    tracemalloc.start()
    started = time.perf_counter()
    main = validate_module1_ref_runtime("ref3_read")
    ref45 = require_module1_ref45_runtime("approved")
    ref6 = require_module1_ref6_runtime("approved")
    current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return {
        "load_ms": _milliseconds(started),
        "current_kib": round(current / 1024, 1),
        "peak_kib": round(peak / 1024, 1),
        "main_status": main.status,
        "ref45_profiles": len(ref45.material_type_profiles),
        "ref45_aliases": len(ref45.alias_rules),
        "ref6_works": len(ref6.work_profiles),
        "ref6_mappings": len(ref6.safe_hints) + len(ref6.conditional_hints) + len(ref6.review_mappings),
    }


def _measure_synthetic() -> dict[str, Any]:
    counts = Counter()
    identities: set[str] = set()
    with _setting("MODULE1_REF45_MODE", "approved"):
        clear_module1_ref45_runtime_cache()
        started = time.perf_counter()
        for index in range(1000):
            raw = _raw_item(index)
            report = build_normalization_report(raw)
            identity = str((raw.raw_payload or {}).get("external_id"))
            counts["ready" if report.is_ready_for_matching else "review"] += 1
            counts["duplicate"] += int(identity in identities)
            identities.add(identity)
        duration = _milliseconds(started)
    clear_module1_ref45_runtime_cache()
    return {
        "observations": 1000,
        "duration_ms": duration,
        "ready": counts["ready"],
        "review": counts["review"],
        "duplicate_observations": counts["duplicate"],
        "unique_source_identities": len(identities),
        "database_writes": 0,
    }


def _measure_queries() -> dict[str, Any]:
    operations: list[str] = []

    def capture(
        connection: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        operations.append(statement.lstrip().split(None, 1)[0].lower())

    result: dict[str, Any] = {}
    event.listen(engine.sync_engine, "before_cursor_execute", capture)
    try:
        with TestClient(app) as client:
            result["anonymous_material_hub_status"] = client.get(VIEW_PATHS[0]).status_code
            app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
                id="00000000-0000-0000-0000-000000000001",
                role=UserRole.ADMIN,
                roleCode=UserRole.ADMIN.value,
            )
            for path in VIEW_PATHS:
                operations.clear()
                response = client.get(path)
                result[path] = {
                    "status": response.status_code,
                    "queries": len(operations),
                    "operations": dict(Counter(operations)),
                }
    finally:
        app.dependency_overrides.pop(get_current_user, None)
        event.remove(engine.sync_engine, "before_cursor_execute", capture)
    return result


def _measure_import() -> dict[str, Any]:
    started = time.perf_counter()
    completed = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return {
        "duration_ms": _milliseconds(started),
        "exit_code": completed.returncode,
        "stderr_lines": len(completed.stderr.splitlines()),
    }


def main() -> int:
    logging.disable(logging.CRITICAL)
    payload = {
        "schema_version": "module1.production-readiness-benchmark.v1",
        "environment_specific_not_sla": True,
        "import": _measure_import(),
        "ref_runtime": _measure_ref_runtime(),
        "memory": _measure_memory(),
        "synthetic": _measure_synthetic(),
        "queries": _measure_queries(),
    }
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
