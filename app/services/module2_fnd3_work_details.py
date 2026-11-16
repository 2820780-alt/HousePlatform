"""Prepare reviewed FND-2 work candidates on four existing draft technologies."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from sqlalchemy import select, text

from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_technology import Technology, TechnologyWorkStep
from app.services.audit_service import log_event
from app.services.module1_fnd2_works import REVIEWED_MATCHES, WorkCandidate
from app.services.module2_fnd3_work_policy import FOUNDATION_BUNDLED_WORK

SOURCE = Path(__file__).resolve().parents[2] / "src/modules/module1/seeds/fnd2_candidates.json"

# Each entry remains conditional: pile methods and separately priced operations
# are alternatives until their project and offer scope has been specified.
DETAILS = {
    "FND_PILE_GRILLAGE": (1, 3, 4, 5, 6, 7, 10, 11, 26, 28, 29, 30, 31, 32, 33, 34,
                          14, 16, 17, 19, 20, 21, 15, 25, 8, 9),
    "FND_SUBSTRUCTURE_WATERPROOFING_COATING": (35, 36, 41, 42),
    "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE": (38, 39, 41),
    "FND_SUBSTRUCTURE_INSULATION_XPS": (43, 44),
}
DETAIL_CONDITION = "Только при назначении проектом и отдельном учёте; состав ставки требует проверки."


def candidates() -> dict[str, WorkCandidate]:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))["works"]
    result = {row[0]: WorkCandidate(*row) for row in source}
    if len(result) != 54 or len(source) != 54:
        raise ValueError("Expected the 54 reviewed FND-2 work candidates")
    return result


async def _resolve(db, items: dict[str, WorkCandidate], *, numbers: set[int] | None = None) -> dict[str, str]:
    numbers = numbers if numbers is not None else {number for values in DETAILS.values() for number in values}
    works = list((await db.scalars(select(WorkCatalogItem).where(WorkCatalogItem.status != "ARCHIVED"))).all())
    by_code = {work.work_code: work for work in works}
    by_name_unit = {}
    for work in works:
        by_name_unit.setdefault((work.work_name.strip().casefold(), work.default_unit), []).append(work)
    codes = {}
    for number in sorted(numbers):
        key = f"FND-WK-{number:03d}"
        item = items[key]
        unit = "linear_meter" if item.unit == "m" else item.unit
        mapped = REVIEWED_MATCHES.get(key)
        if mapped:
            matches = [by_code[mapped]] if mapped in by_code else []
        else:
            work_id = "fnd2_" + uuid.uuid5(uuid.NAMESPACE_URL, f"atom/work/{item.name.casefold()}/{unit}").hex
            exact = by_name_unit.get((item.name.strip().casefold(), unit), [])
            if len(exact) > 1:
                raise ValueError(f"Reviewed work is ambiguous: {key}")
            known = by_code.get(work_id)
            if known:
                matches = [known]
            else:
                matches = exact
        if len(matches) != 1 or matches[0].default_unit != unit:
            raise ValueError(f"Reviewed work is missing or ambiguous: {key}")
        if not mapped and matches[0].work_name.strip().casefold() != item.name.strip().casefold():
            raise ValueError(f"Reviewed work identity changed: {key}")
        codes[key] = matches[0].work_code
    return codes


async def add_foundation_work_details(db) -> dict:
    """Add conditional steps to four drafts; preserve original bundled steps."""
    if db.bind.dialect.name != "postgresql":
        raise ValueError("Foundation detail requires PostgreSQL transaction locking")
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd3.work.details'))"))
    items = candidates()
    codes = await _resolve(db, items)
    technologies = list((await db.scalars(select(Technology).where(
        Technology.status == "DRAFT", Technology.technology_code.in_(DETAILS)).with_for_update())).all())
    by_code = {tech.technology_code: tech for tech in technologies}
    if len(technologies) != len(DETAILS) or len(by_code) != len(DETAILS):
        raise ValueError("Expected one DRAFT per foundation technology")
    results = {}
    for code, numbers in DETAILS.items():
        technology = by_code[code]
        existing = list((await db.scalars(select(TechnologyWorkStep).where(
            TechnologyWorkStep.technology_id == technology.id).order_by(TechnologyWorkStep.position))).all())
        if not any(row.work_code == FOUNDATION_BUNDLED_WORK[code] for row in existing):
            raise ValueError(f"Expected bundled step missing: {code}")
        present = {row.work_code for row in existing}
        position = max((row.position for row in existing), default=0)
        created = 0
        grouped = {}
        for number in numbers:
            key = f"FND-WK-{number:03d}"
            work_code = codes[key]
            grouped.setdefault(work_code, []).append(items[key])
        for work_code, work_items in grouped.items():
            if work_code in present:
                continue
            position += 1
            db.add(TechnologyWorkStep(
                id=uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd2/{technology.id}/work/{work_code}"),
                technology_id=technology.id, position=position, work_code=work_code,
                applicability_expression=DETAIL_CONDITION, dependency_step_codes=[],
                instructions="\n".join(dict.fromkeys(part for item in work_items
                                                     for part in (item.applicability, item.note) if part)),
            ))
            present.add(work_code)
            created += 1
        await db.flush()
        if created:
            await log_event(db, "M2_FND3_CONDITIONAL_WORK_DETAILS", "Technology", technology.id, None,
                            {"created": created, "bundle_retained": True})
        results[code] = {"created": created, "steps": len(present), "bundle_retained": True}
    return results
