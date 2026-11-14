"""Run the FND-2 work import only against the isolated vertical QA database."""
import asyncio
from pathlib import Path

import vertical_qa_server  # configures and verifies the isolated database
from openpyxl import load_workbook
from app.database import async_session_factory
from app.services.module1_fnd2_works import WorkCandidate, import_work_candidates


async def main():
    workbook = load_workbook(Path(__file__).with_name("fnd2-source.xlsx"), read_only=True, data_only=True)
    try:
        rows = workbook["Работы_кандидаты"].iter_rows(min_row=4, values_only=True)
        candidates = [WorkCandidate(*(str(row[i] or "").strip() for i in (0, 2, 3, 4, 5, 6, 10))) for row in rows]
    finally:
        workbook.close()
    async with async_session_factory() as db:
        first = await import_work_candidates(db, candidates)
        await db.commit()
        second = await import_work_candidates(db, candidates)
        await db.rollback()
        if second["created"] != 0 or second["reused"] != 54 or first["work_codes"] != second["work_codes"]:
            raise RuntimeError("FND-2 work import is not idempotent")
        print(f"QA: created={first['created']}, reused={first['reused']}; repeat reused={second['reused']}")


if __name__ == "__main__":
    asyncio.run(main())
