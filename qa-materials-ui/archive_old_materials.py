"""Archive the June 2026 M1 test cohort, preserving referenced material records."""

import argparse
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path
from uuid import UUID

from pydantic_settings import BaseSettings
from sqlalchemy import column, select, table, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy.sql import quoted_name

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
parser = argparse.ArgumentParser()
parser.add_argument("--database", choices=("buildplatform", "houseplatform_m1archive_check_20261111"), required=True)
parser.add_argument("--fingerprint", required=True)
parser.add_argument("--commit", action="store_true")
parser.add_argument("--remaining", action="store_true")
args = parser.parse_args()
original_init = BaseSettings.__init__


def no_env_file(self, *values, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *values, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=args.database).render_as_string(hide_password=False)

from app.config import settings
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module2_material_gap import Module2MaterialGap
from app.models.module2_technology import TechnologyDefaultAssumption, TechnologyMaterialRequirement
from app.services.audit_service import log_event
from app.services.module1_foundation_target_package import (
    M1_HISTORY_REFERENCES,
    _externally_referenced_material_ids,
    _m2_json_referenced_material_ids,
    material_inventory_fingerprint,
)


async def other_external_references(db, active_ids):
    rows = (await db.execute(text("""
        SELECT child_ns.nspname, child.relname, child_attr.attname
        FROM pg_catalog.pg_constraint c
        JOIN pg_catalog.pg_class parent ON parent.oid = c.confrelid
        JOIN pg_catalog.pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
        JOIN pg_catalog.pg_class child ON child.oid = c.conrelid
        JOIN pg_catalog.pg_namespace child_ns ON child_ns.oid = child.relnamespace
        CROSS JOIN LATERAL unnest(c.conkey, c.confkey) AS k(child_number, parent_number)
        JOIN pg_catalog.pg_attribute child_attr ON child_attr.attrelid = child.oid AND child_attr.attnum = k.child_number
        JOIN pg_catalog.pg_attribute parent_attr ON parent_attr.attrelid = parent.oid AND parent_attr.attnum = k.parent_number
        WHERE c.contype = 'f' AND parent_ns.nspname = 'public'
          AND parent.relname = 'materials' AND parent_attr.attname = 'id'
    """))).all()
    if not rows:
        raise RuntimeError("Material foreign-key inventory is empty")
    result = set()
    history = M1_HISTORY_REFERENCES | {("public", "rule_memory", "material_id"),
                                      ("public", "supplier_upload_rows", "material_id")}
    for schema, name, field_name in rows:
        if (schema, name, field_name) in history:
            continue
        relation = table(quoted_name(name, True), column(quoted_name(field_name, True)), schema=quoted_name(schema, True))
        field = relation.c[field_name]
        result.update((await db.scalars(select(field).where(field.in_(active_ids)).distinct())).all())
    return result


async def main():
    if make_url(settings.DATABASE_URL).database != args.database:
        raise RuntimeError("Unexpected database")
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.fnd.m1.targets.20261110'))"))
            await db.execute(text("SET LOCAL lock_timeout = '3s'"))
            await db.execute(text("LOCK TABLE public.materials, public.material_attributes, "
                                  "public.module2_technology_default_assumptions IN EXCLUSIVE MODE"))
            await db.execute(text("LOCK TABLE public.module2_technology_material_requirements, public.module2_technology_layers, "
                                  "public.module2_technology_nodes, public.module2_technology_work_steps, "
                                  "public.module2_consumption_norms, public.module2_compatibility_rules, "
                                  "public.module2_knowledge_rules, public.module2_material_gaps IN SHARE MODE"))
            materials = list((await db.scalars(select(Material).options(selectinload(Material.attributes)))).all())
            if len(materials) != 394 or await material_inventory_fingerprint(db) != args.fingerprint:
                raise RuntimeError("Material inventory differs from the backup; refusing to archive")
            active = [item for item in materials if item.status not in {MaterialStatus.ARCHIVED, MaterialStatus.REJECTED}]
            if len(active) != (2 if args.remaining else 332) or any(item.created_at.date() > date(2026, 6, 19) for item in active):
                raise RuntimeError("Active material cohort changed; refusing to archive")
            protected = set((await db.scalars(select(TechnologyMaterialRequirement.canonical_material_id)
                              .where(TechnologyMaterialRequirement.canonical_material_id.is_not(None)))).all())
            if args.remaining:
                protected.update(await other_external_references(db, {item.id for item in active}))
            else:
                protected.update(await _externally_referenced_material_ids(db))
            protected.update(await _m2_json_referenced_material_ids(db, {item.id for item in materials}))
            protected.update((await db.scalars(select(Module2MaterialGap.resolved_material_id)
                              .where(Module2MaterialGap.resolved_material_id.is_not(None)))).all())
            assumptions = (await db.scalars(select(TechnologyDefaultAssumption).where(
                TechnologyDefaultAssumption.status == "ACTIVE", TechnologyDefaultAssumption.value_type == "MATERIAL"))).all()
            for assumption in assumptions:
                protected.add(UUID(str((assumption.default_value or {}).get("value"))))
            retained = [item for item in active if item.id in protected]
            if args.remaining and retained:
                raise RuntimeError("Remaining materials have additional protected references")
            for material in active:
                if material.id in protected:
                    continue
                previous = material.status.value
                material.status = MaterialStatus.ARCHIVED
                await log_event(db, "M1_TEST_MATERIAL_ARCHIVED", "Material", material.id, None,
                                {"reason": "June 2026 test catalogue", "old_status": previous, "reversible": True})
            await db.flush()
            result = {"archived": len(active) - len(retained), "protected": len(retained),
                      "protected_names": [item.canonical_name for item in retained], "committed": args.commit}
            if args.commit:
                await db.commit()
            else:
                await db.rollback()
            print(json.dumps(result, ensure_ascii=False))
    finally:
        await engine.dispose()


asyncio.run(main())
