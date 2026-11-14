"""Convert the supplied workbook into a reviewed, reproducible FND-2 input."""
import json
import sys
from pathlib import Path
from openpyxl import load_workbook

root = Path(__file__).resolve().parent.parent
destination = root / "src/modules/module1/seeds/fnd2_candidates.json"
if destination.exists() and "--refresh" not in sys.argv:
    raise RuntimeError("Refusing to overwrite an existing source package")
book = load_workbook(root / "qa-materials-ui/fnd2-source.xlsx", read_only=True, data_only=True)
try:
    materials = [[str(value or "").strip() for value in row[:5]]
                 for row in book["Материалы_создать"].iter_rows(min_row=4, values_only=True)]
    works = [[str(row[i] or "").strip() for i in (0, 2, 3, 4, 5, 6, 10)]
             for row in book["Работы_кандидаты"].iter_rows(min_row=4, values_only=True)]
    existing = [[str(value or "").strip() for value in row[:3]]
                for row in book["M1_существующие"].iter_rows(min_row=4, values_only=True)]
    unresolved = [[str(value or "").strip() for value in row[:6]]
                  for row in book["Материалы_уточнить"].iter_rows(min_row=4, values_only=True)]
finally:
    book.close()
if (len(materials), len(works), len(existing), len(unresolved)) != (34, 54, 67, 13):
    raise ValueError("Unexpected workbook dimensions")
destination.write_text(json.dumps({"materials": materials, "works": works, "existing": existing, "unresolved": unresolved},
                                  ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print("Exported 34 material candidates, 54 work candidates, 67 identities and 13 unresolved roles")
