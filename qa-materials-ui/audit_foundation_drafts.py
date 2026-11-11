"""Evaluate incomplete foundation role coverage in a rolled-back QA transaction."""

import asyncio
import json
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
DATABASE = "houseplatform_m1archive_check_20261111"
original_init = BaseSettings.__init__


def no_env_file(self, *values, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *values, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=DATABASE).render_as_string(hide_password=False)

from app.config import settings
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module2_technology import Technology
from app.services.module1_foundation_target_package import PACKAGE
from app.services.module2_foundation_preliminary_profiles import (
    PROFILES, audit_profile_reconciliation, populate_blocked_foundation_draft, prepare_single_role_linkage_draft,
)
from app.services.module2_technology_foundation import read_technology
from app.services.module2_foundation_integration import prepare_partial_foundation_drafts


async def main():
    if make_url(settings.DATABASE_URL).database != DATABASE:
        raise RuntimeError("Unexpected database")
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as db:
            materials = (await db.scalars(select(Material).where(Material.status == MaterialStatus.DRAFT)
                        .options(selectinload(Material.attributes)))).all()
            by_code = {}
            for material in materials:
                values = {item.attribute_name: item.attribute_value for item in material.attributes}
                if values.get("registry_origin") == PACKAGE and values.get("registry_code"):
                    by_code[values["registry_code"]] = material
            codes = {profile.technology_code for profile in PROFILES}
            active = (await db.scalars(select(Technology).where(Technology.technology_code.in_(codes),
                                       Technology.status == "ACTIVE"))).all()
            if len(active) != len(codes):
                raise RuntimeError("Unexpected active technology inventory")
            reports = []
            for item in active:
                technology = await read_technology(db, item.id)
                draft, linked, unresolved = prepare_single_role_linkage_draft(
                    technology, by_code, actor_role_code="ENGINEER_DESIGNER")
                report = populate_blocked_foundation_draft(draft, by_code, actor_role_code="ENGINEER_DESIGNER")
                profile = next(profile for profile in PROFILES if profile.technology_code == item.technology_code)
                roles = {role.code: role for role in profile.roles}
                suggested = dict(audit_profile_reconciliation(technology).suggested_expansions)
                legacy_details = []
                for requirement in technology.requirements:
                    if requirement.code not in unresolved:
                        continue
                    role_codes = suggested.get(requirement.code, ())
                    if not role_codes:
                        reason = "Не определено смысловое соответствие новой роли."
                    elif len(role_codes) > 1:
                        reason = "Требуется согласовать составные роли: " + ", ".join(role_codes) + "."
                    elif not roles[role_codes[0]].material_code:
                        reason = roles[role_codes[0]].missing or "Для роли не выбран конкретный материал."
                    elif roles[role_codes[0]].material_code not in by_code:
                        reason = f"Профиль M1 {roles[role_codes[0]].material_code} не входит в подготовленный выпуск."
                    else:
                        reason = "Не совпадают исходный селектор или категория; требуется предметная сверка."
                    legacy_details.append({"code": requirement.code, "reason": reason})
                details = [{"code": code, "purpose": roles[code].purpose,
                            "reason": roles[code].missing or "Требуется сверка материала, состава роли и расчётного правила.",
                            } for code in report["unresolved"] if code in roles]
                reports.append({"technology": item.technology_code, "legacy_linked": len(linked),
                                "legacy_unresolved": list(unresolved), "added_roles": len(report["added_roles"]),
                                "unresolved": list(report["unresolved"]), "details": details,
                                "legacy_details": legacy_details, "conflicts": list(report["conflicts"])})
            snapshot = {item.technology_code: (item.id, item.revision) for item in active}
            prepared = await prepare_partial_foundation_drafts(
                db, expected_active_revisions=snapshot, actor_role_code="ENGINEER_DESIGNER")
            if prepared["drafts"] != len(codes):
                raise RuntimeError("Incomplete draft set")
            await db.rollback()
            print(json.dumps(reports, ensure_ascii=False, default=str))
    finally:
        await engine.dispose()


asyncio.run(main())
