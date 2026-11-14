"""Map the reviewed FND-2 operations to the existing M1 work catalog."""
from __future__ import annotations

from dataclasses import dataclass
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import select, text

from app.models.module1_work_item import WorkCatalogItem
from app.services.module1_work_catalog import get_work_catalog_registry
from app.services.module1_work_catalog_store import WorkCatalogWrite, save_work_item


@dataclass(frozen=True)
class WorkCandidate:
    key: str
    name: str
    group: str
    unit: str
    basis: str
    applicability: str
    note: str


# Explicit matches share both the operation and measurement basis; broader or
# differently measured operations are intentionally not inferred as matches.
REVIEWED_MATCHES = {
    "FND-WK-003": "earthworks_razrabotka_grunta_tehnikoy",
    "FND-WK-004": "earthworks_razrabotka_grunta_tehnikoy",
    "FND-WK-005": "earthworks_razrabotka_grunta_vruchnuyu",
    "FND-WK-007": "earthworks_vyvoz_grunta",
    "FND-WK-008": "earthworks_obratnaya_zasypka",
    "FND-WK-010": "earthworks_ustroystvo_peschanoy_podushki",
    "FND-WK-011": "earthworks_ustroystvo_schebenochnoy_podushki",
    "FND-WK-012": "earthworks_ukladka_geotekstilya",
    "FND-WK-014": "foundations_concrete_montazh_opalubki_fundamenta",
    "FND-WK-015": "foundations_concrete_demontazh_opalubki",
    "FND-WK-017": "reinforcement_armirovanie_fundamenta",
    "FND-WK-020": "foundations_concrete_betonirovanie_konstrukciy",
    "FND-WK-022": "foundations_concrete_montazh_blokov_fbs",
    "FND-WK-023": "foundations_concrete_montazh_fundamentnyh_plit_fl",
    "FND-WK-029": "foundations_concrete_pogruzhenie_zhelezobetonnyh_svay",
    "FND-WK-031": "foundations_concrete_montazh_vintovyh_svay",
}


async def import_work_candidates(db, candidates: list[WorkCandidate]) -> dict:
    if len(candidates) != 54 or len({c.key for c in candidates}) != 54:
        raise ValueError("Expected exactly 54 distinct reviewed work candidates")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.m1.work.catalog.write'))"))
    registry = get_work_catalog_registry()
    groups = {g.work_group: g.work_category for g in registry.groups}
    items = list((await db.scalars(select(WorkCatalogItem).where(WorkCatalogItem.status != "ARCHIVED"))).all())
    by_code = {item.work_code: item for item in items}
    result = {"created": 0, "reused": 0, "work_codes": {}}
    for candidate in candidates:
        if not all((candidate.key, candidate.name, candidate.group, candidate.unit, candidate.basis)):
            raise ValueError("Incomplete work candidate")
        unit = "linear_meter" if candidate.unit == "m" else candidate.unit
        mapped = REVIEWED_MATCHES.get(candidate.key)
        if mapped:
            item = by_code.get(mapped)
            if item is None or item.default_unit != unit:
                raise ValueError(f"Reviewed work missing or has different unit: {candidate.key}")
        else:
            matches = [item for item in items if item.work_name.casefold().strip() == candidate.name.casefold().strip()
                       and item.default_unit == unit]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous work identity: {candidate.key}")
            item = matches[0] if matches else None
        if item is None:
            group = "earthworks" if candidate.group == "Геодезия и земляные" else (
                "reinforcement" if candidate.group == "Армирование" else "foundations_concrete")
            code = "fnd2_" + uuid5(NAMESPACE_URL, f"atom/work/{candidate.name.casefold()}/{unit}").hex
            if code in by_code:
                raise ValueError(f"Work ID collision: {candidate.key}")
            payload = WorkCatalogWrite(work_code=code, work_group=group, work_category=groups[group],
                work_name=candidate.name, default_unit=unit, allowed_units=[unit], applies_to="private_house",
                description=candidate.note or None,
                conditions={"quantity_basis": candidate.basis, "applicability": candidate.applicability})
            item = await save_work_item(db, payload, actor_id=None)
            items.append(item)
            by_code[item.work_code] = item
            result["created"] += 1
        else:
            result["reused"] += 1
        result["work_codes"][candidate.key] = item.work_code
    return result
