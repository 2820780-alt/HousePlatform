"""Create a deterministic copy of one M2 revision for M5."""
from __future__ import annotations

import hashlib
import json

from app.schemas.module2_calculation_package_v2 import CalculationPackageBlockV2, CalculationPackageV2
from app.services.module2_calculation_blocks import decode_definition


def build_calculation_package_v2(technology, rows) -> tuple[CalculationPackageV2, str]:
    blocks = []
    for row in rows:
        if row.technology_id != technology.id:
            raise ValueError("calculation block belongs to a different technology revision")
        decode_definition(row.definition, block_id=str(row.id), name=row.name,
                          material_id=str(row.material_id) if row.material_id else None, work_code=row.work_code)
        blocks.append(CalculationPackageBlockV2(id=row.id, version=row.version, position=row.position, name=row.name,
            material_id=row.material_id, work_code=row.work_code, definition=row.definition))
    blocks.sort(key=lambda item: (item.position, str(item.id)))
    if len({item.id for item in blocks}) != len(blocks) or len({item.position for item in blocks}) != len(blocks):
        raise ValueError("calculation package has duplicate block IDs or positions")
    package = CalculationPackageV2(technology_id=technology.id, technology_code=technology.technology_code,
        technology_revision=technology.revision, technology_status=technology.status, blocks=tuple(blocks))
    encoded = json.dumps(package.model_dump(mode="json"), ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return package, hashlib.sha256(encoded.encode("utf-8")).hexdigest()
