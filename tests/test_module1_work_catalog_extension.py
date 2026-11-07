from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.services.module1_ref6_work_material_policy import resolve_work_material_hints
from app.services.module1_work_catalog import (
    WorkCatalogError,
    get_work_item,
    load_effective_work_catalog,
    load_work_catalog_seed,
)


BASELINE = Path("src/modules/module1/seeds/work_catalog_seed.json")
EXTENSION = Path("src/modules/module1/seeds/work_catalog_extensions/foundations_a2_v1.json")
NEW_CODES = (
    "foundations_concrete_montazh_fundamentnyh_plit_fl",
    "foundations_concrete_montazh_blokov_fbs",
    "foundations_concrete_pogruzhenie_zhelezobetonnyh_svay",
)


def test_ref6_baseline_is_unchanged_and_extension_is_additive():
    baseline = load_work_catalog_seed(BASELINE)
    effective = load_effective_work_catalog(BASELINE, (EXTENSION,))
    assert baseline.version == "1.0"
    assert len(baseline.works) == 209
    assert effective.version == "1.1"
    assert len(effective.works) == 212
    assert effective.works[:209] == baseline.works
    assert tuple(item.work_code for item in effective.works[209:]) == NEW_CODES
    assert len({item.work_code for item in effective.works}) == 212
    assert all(get_work_item(code) is not None for code in NEW_CODES)
    approval_record = json.loads(EXTENSION.read_text(encoding="utf-8"))["approval_record"]
    assert Path(approval_record).is_file()


def test_extension_rejects_duplicate_and_unapproved_baseline(tmp_path):
    raw = json.loads(EXTENSION.read_text(encoding="utf-8"))
    raw["works"][0]["work_code"] = load_work_catalog_seed(BASELINE).works[0].work_code
    duplicate = tmp_path / "duplicate.json"
    duplicate.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(WorkCatalogError, match="duplicates work code"):
        load_effective_work_catalog(BASELINE, (duplicate,))

    raw["works"][0]["work_code"] = NEW_CODES[0]
    raw["baseline_sha256_lf"] = "0" * 64
    mismatched = tmp_path / "mismatched.json"
    mismatched.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(WorkCatalogError, match="provenance"):
        load_effective_work_catalog(BASELINE, (mismatched,))

    raw["baseline_sha256_lf"] = json.loads(EXTENSION.read_text(encoding="utf-8"))[
        "baseline_sha256_lf"
    ]
    raw["approval_record"] = "unapproved.md"
    unapproved = tmp_path / "unapproved.json"
    unapproved.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(WorkCatalogError, match="approval record"):
        load_effective_work_catalog(BASELINE, (unapproved,))


def test_extension_material_hints_fail_closed_in_approved_mode():
    for code in NEW_CODES:
        result = resolve_work_material_hints(code, mode="approved")
        assert result.known_work is True
        assert result.state == "review_required"
        assert result.hints == tuple()
        assert result.database_write_allowed is False
        assert result.quantity_calculation_allowed is False
        assert result.module5_costing_allowed is False
    assert resolve_work_material_hints("not_a_work_code", mode="approved").state == "unknown_work"
