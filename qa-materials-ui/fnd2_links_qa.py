"""Verify candidate links only in the restored vertical QA database."""
import asyncio
from pathlib import Path
from uuid import UUID

import vertical_qa_server  # configures and verifies the isolated database
from openpyxl import load_workbook
from app.database import async_session_factory
from app.models.material import Material
from app.services.module1_fnd2_materials import MaterialCandidate, import_material_candidates
from app.services.module1_material_normalizer import normalize_title
from app.services.module2_fnd2_material_links import link_material_choices


async def main():
    workbook = load_workbook(Path(__file__).with_name("fnd2-source.xlsx"), read_only=True, data_only=True)
    try:
        new_rows = workbook["Материалы_создать"].iter_rows(min_row=4, values_only=True)
        candidates = [MaterialCandidate(*(str(value or "").strip() for value in row[:5])) for row in new_rows]
        existing_rows = list(workbook["M1_существующие"].iter_rows(min_row=4, values_only=True))
    finally:
        workbook.close()
    async with async_session_factory() as db:
        imported = await import_material_candidates(db, candidates)
        ids = imported["material_ids"]
        for row in existing_rows:
            key, name, identifier = (str(value or "").strip() for value in row[:3])
            material = await db.get(Material, UUID(identifier))
            if not material or normalize_title(material.canonical_name).casefold() != normalize_title(name).casefold():
                raise ValueError(f"Existing material identity changed: {key}")
            ids[key] = identifier
        first = await link_material_choices(db, material_ids=ids)
        await db.commit()
        second = await link_material_choices(db, material_ids=ids)
        await db.rollback()
        if any(row["created"] for row in second.values()):
            raise RuntimeError("FND-2 material links are not idempotent")
        print(f"QA: technologies={len(first)}; created={sum(row['created'] for row in first.values())}; "
              f"reused={sum(row['reused'] for row in first.values())}; repeat_created=0")


if __name__ == "__main__":
    asyncio.run(main())
