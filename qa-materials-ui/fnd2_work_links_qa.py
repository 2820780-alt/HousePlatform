"""Verify ordered work links only in the restored vertical QA database."""
import asyncio
from pathlib import Path

import vertical_qa_server  # configures and verifies the isolated database
from openpyxl import load_workbook
from app.database import async_session_factory
from app.services.module1_fnd2_works import WorkCandidate, import_work_candidates
from app.services.module2_fnd2_work_links import link_work_choices


async def main():
    workbook = load_workbook(Path(__file__).with_name("fnd2-source.xlsx"), read_only=True, data_only=True)
    try:
        rows = workbook["Работы_кандидаты"].iter_rows(min_row=4, values_only=True)
        candidates = [WorkCandidate(*(str(row[i] or "").strip() for i in (0, 2, 3, 4, 5, 6, 10))) for row in rows]
    finally:
        workbook.close()
    async with async_session_factory() as db:
        works = await import_work_candidates(db, candidates)
        first = await link_work_choices(db, work_codes=works["work_codes"],
                                        work_notes={work.key: work.note for work in candidates})
        await db.commit()
        second = await link_work_choices(db, work_codes=works["work_codes"],
                                         work_notes={work.key: work.note for work in candidates})
        await db.rollback()
        if any(row["created"] for row in second.values()):
            raise RuntimeError("FND-2 work links are not idempotent")
        print(f"QA: technologies={len(first)}; created={sum(row['created'] for row in first.values())}; "
              f"bundle_review={sum(row['bundled_scope_review'] for row in first.values())}; repeat_created=0")


if __name__ == "__main__":
    asyncio.run(main())
