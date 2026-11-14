"""Run the FND-2 material import only against the isolated vertical QA database."""
import asyncio
from pathlib import Path

import vertical_qa_server  # sets and verifies the isolated database before application imports
from openpyxl import load_workbook
from app.database import async_session_factory
from app.services.module1_fnd2_materials import MaterialCandidate, import_material_candidates


async def main():
    workbook = load_workbook(Path(__file__).with_name("fnd2-source.xlsx"), read_only=True, data_only=True)
    try:
        rows = workbook["Материалы_создать"].iter_rows(min_row=4, values_only=True)
        candidates = [MaterialCandidate(*(str(value or "").strip() for value in row[:5])) for row in rows]
    finally:
        workbook.close()
    async with async_session_factory() as db:
        first = await import_material_candidates(db, candidates)
        await db.commit()
        second = await import_material_candidates(db, candidates)
        await db.rollback()
        if second["created"] != 0 or second["reused"] != 34 or first["material_ids"] != second["material_ids"]:
            raise RuntimeError("FND-2 material import is not idempotent")
        print(f"QA: created={first['created']}, reused={first['reused']}; repeat reused={second['reused']}")


if __name__ == "__main__":
    asyncio.run(main())
