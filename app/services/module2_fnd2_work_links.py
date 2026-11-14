"""Conservative ordered work choices for foundation technology drafts."""
from __future__ import annotations

import uuid
from sqlalchemy import select, text

from app.models.module1_work_item import WorkCatalogItem
from app.models.module2_technology import Technology, TechnologyWorkStep
from app.services.audit_service import log_event


# Detailed waterproofing and pile-grillage work is intentionally not appended
# beside existing bundled work until the bundle's scope has been resolved.
WORKS = {
    "FND_STRIP_MONOLITHIC_RC": (1, 2, 4, 5, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 15, 36, 43, 8, 9),
    "FND_STRIP_PRECAST_FBS_FL": (1, 2, 4, 5, 6, 7, 10, 11, 12, 13, 23, 22, 24, 25, 36, 8, 9),
    "FND_SLAB_MONOLITHIC_RC": (1, 2, 3, 5, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 15, 36, 43, 8, 9),
    "FND_SLAB_RIBBED_RC": (1, 2, 3, 5, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 15, 8, 9),
    "FND_SLAB_USHP": (1, 2, 3, 5, 6, 7, 10, 11, 12, 13, 43, 14, 16, 17, 19, 49, 50, 51, 53, 54, 20, 21, 15, 8, 9),
    "FND_UFF": (1, 2, 4, 5, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 15, 43, 49, 50, 51, 52, 53, 54, 8, 9),
    "FND_PILE_BORED_RC": (1, 2, 6, 7, 26, 27, 17, 19, 20, 21),
    "FND_PILE_DRIVEN_RC": (1, 2, 29, 30),
    "FND_PILE_SCREW": (1, 2, 31, 32, 33, 34),
    "FND_PILE_GRILLAGE": (),
    "FND_COLUMN_CONCRETE_RC": (1, 2, 3, 5, 6, 7, 10, 11, 12, 13, 14, 16, 17, 19, 20, 21, 15, 8, 9),
    "FND_BASEMENT_WALL_MONOLITHIC": (1, 2, 3, 5, 6, 7, 14, 16, 17, 19, 20, 21, 15, 49, 50, 45, 46, 47, 48, 8, 9),
    "FND_SUBSTRUCTURE_WATERPROOFING_COATING": (),
    "FND_SUBSTRUCTURE_WATERPROOFING_MEMBRANE": (),
    "FND_SUBSTRUCTURE_INSULATION_XPS": (),
}

ALIASES = {
    "reinforcement_armirovanie_plity": 17,
    "foundations_concrete_burenie_pod_svai": 26,
    "foundations_concrete_gidroizolyaciya_fundamenta": 36,
    "foundations_concrete_uteplenie_fundamenta": 43,
}
BUNDLE_NOTE = "Состав укрупнённой работы требует уточнения; не суммировать с её отдельными операциями."


async def link_work_choices(db, *, work_codes: dict[str, str], work_notes: dict[str, str] | None = None) -> dict:
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd2.technology.works'))"))
    technologies = list((await db.scalars(select(Technology).where(
        Technology.status == "DRAFT", Technology.technology_code.in_(WORKS)).with_for_update())).all())
    by_code = {tech.technology_code: tech for tech in technologies}
    if len(technologies) != 15 or len(by_code) != 15:
        raise ValueError("Expected exactly one DRAFT for each of 15 foundation technologies")
    required = {f"FND-WK-{number:03d}" for numbers in WORKS.values() for number in numbers}
    if required - set(work_codes):
        raise ValueError("Required work candidates have not been resolved")
    available = set((await db.scalars(select(WorkCatalogItem.work_code).where(
        WorkCatalogItem.work_code.in_(work_codes.values()), WorkCatalogItem.status != "ARCHIVED"))).all())
    if {work_codes[key] for key in required} - available:
        raise ValueError("A referenced work is missing or archived")
    results = {}
    for code, numbers in WORKS.items():
        tech = by_code[code]
        rows = list((await db.scalars(select(TechnologyWorkStep).where(
            TechnologyWorkStep.technology_id == tech.id).order_by(TechnologyWorkStep.position))).all())
        if not numbers:
            if not rows:
                raise ValueError(f"Bundled work is missing from {code}")
            if BUNDLE_NOTE not in (rows[0].instructions or ""):
                rows[0].instructions = ((rows[0].instructions or "").rstrip() + "\n" + BUNDLE_NOTE).strip()
        existing = {row.work_code: row for row in rows}
        planned, seen = [], set()
        for number in numbers:
            source_key = f"FND-WK-{number:03d}"
            work_code = work_codes[source_key]
            alias = next((item for item in rows if ALIASES.get(item.work_code) == number), None)
            row = existing.get(work_code) or alias
            if row is None:
                row = TechnologyWorkStep(id=uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd2/{tech.id}/work/{work_code}"),
                    technology_id=tech.id, position=100000 + len(planned), work_code=work_code,
                    applicability_expression="Только при назначении проектом и отдельном учёте работы.",
                    dependency_step_codes=[], instructions="Объём и условия определяются проектом; исключить повторный учёт.")
                db.add(row)
                existing[work_code] = row
            if row.id == uuid.uuid5(uuid.NAMESPACE_URL, f"atom/fnd2/{tech.id}/work/{work_code}"):
                note = (work_notes or {}).get(source_key, "").strip()
                if note and note not in (row.instructions or ""):
                    row.instructions = ((row.instructions or "").rstrip() + "\n" + note).strip()
            if row.id not in seen:
                planned.append(row)
                seen.add(row.id)
        # Retain unmatched pre-existing steps; none are removed or replaced.
        planned.extend(row for row in rows if row.id not in seen)
        created = len(planned) - len(rows)
        if created or any(row.position != position for position, row in enumerate(planned, 1)):
            for offset, row in enumerate(rows, 1):
                row.position = 200000 + offset
            await db.flush()
            for position, row in enumerate(planned, 1):
                row.position = position
            await db.flush()
        await log_event(db, "M2_FND2_WORK_CHOICES", "Technology", tech.id, None, {"created": created})
        results[code] = {"created": created, "count": len(planned), "bundled_scope_review": not numbers}
    return results
