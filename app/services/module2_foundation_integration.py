"""Transactional preparation of the reviewed M1/M2 foundation package.

The caller owns the transaction. Created technology revisions are blocked drafts;
this service never publishes them, closes gaps, commits, or starts price collection.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.access_levels import AccessLevel
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.module2_material_gap import Module2MaterialGap
from app.models.module2_technology import Technology
from app.services.module1_foundation_target_package import PACKAGE, apply_foundation_target_package, targets
from app.services.module1_foundation_material_release import releasable_foundation_targets
from app.services.module2_foundation_preliminary_profiles import (
    PROFILES, populate_blocked_foundation_draft, prepare_single_role_linkage_draft,
)
from app.services.module2_technology_foundation import read_technology, require_module2_access


async def prepare_partial_foundation_drafts(
    db: AsyncSession, *, expected_active_revisions: dict[str, tuple[UUID, int]], actor_role_code: str,
) -> dict:
    """Prepare blocked drafts from the available reviewed M1 profiles, preserving unresolved roles."""
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    codes = {profile.technology_code for profile in PROFILES}
    if set(expected_active_revisions) != codes:
        raise ValueError("the reviewed snapshot must identify all foundation technologies")
    active = (await db.scalars(select(Technology).where(
        Technology.technology_code.in_(codes), Technology.status == "ACTIVE").with_for_update())).all()
    if len(active) != len(codes) or {item.technology_code: (item.id, item.revision) for item in active} != expected_active_revisions:
        raise ValueError("active foundation revisions changed since the reviewed snapshot")
    if (await db.scalars(select(Technology.id).where(
            Technology.technology_code.in_(codes), Technology.status.in_(("DRAFT", "REVIEW"))))).first():
        raise ValueError("foundation draft or review revision already exists; do not replace it")
    for item in active:
        if await db.scalar(select(Technology.id).where(
                Technology.technology_code == item.technology_code, Technology.revision == item.revision + 1)):
            raise ValueError("the next foundation revision number is already in use")
    materials = (await db.scalars(select(Material).where(Material.status == MaterialStatus.DRAFT)
                 .options(selectinload(Material.attributes)))).all()
    by_code = {}
    for material in materials:
        values = {attribute.attribute_name: attribute.attribute_value for attribute in material.attributes}
        if values.get("registry_origin") != PACKAGE or not values.get("registry_code"):
            continue
        if values["registry_code"] in by_code:
            raise ValueError("duplicate foundation registry code")
        by_code[values["registry_code"]] = material
    expected_codes = {dict(target.properties).get("registry_code") for target in releasable_foundation_targets()[0]}
    if None in expected_codes or set(by_code) != expected_codes:
        raise ValueError("foundation material profiles are incomplete or have unexpected registry codes")
    gap_count = await db.scalar(select(func.count()).select_from(Module2MaterialGap))
    reports = []
    for item in active:
        technology = await read_technology(db, item.id)
        if technology is None:
            raise ValueError("active foundation technology disappeared")
        draft, linked, unresolved = prepare_single_role_linkage_draft(
            technology, by_code, actor_role_code=actor_role_code)
        report = populate_blocked_foundation_draft(draft, by_code, actor_role_code=actor_role_code)
        if report["conflicts"]:
            raise ValueError(f"foundation draft has conflicting records: {technology.technology_code}")
        db.add(draft)
        reports.append({"technology": item.technology_code, "legacy_linked": list(linked),
                        "legacy_unresolved": list(unresolved), "added_roles": list(report["added_roles"]),
                        "unresolved": list(report["unresolved"])})
    await db.flush()
    if await db.scalar(select(func.count()).select_from(Module2MaterialGap)) != gap_count:
        raise ValueError("existing material gaps changed during preparation")
    return {"drafts": len(reports), "reports": reports, "existing_gaps": gap_count}


async def prepare_foundation_integration(
    db: AsyncSession,
    *,
    expected_existing_materials: int,
    expected_material_fingerprint: str,
    expected_active_revisions: dict[str, tuple[UUID, int]],
    actor_role_code: str,
    acknowledge_test_data: bool = False,
) -> dict:
    """Prepare exactly the inventoried package without committing or activating it."""
    require_module2_access(actor_role_code, AccessLevel.EDIT)
    expected_codes = {profile.technology_code for profile in PROFILES}
    if set(expected_active_revisions) != expected_codes:
        raise ValueError("the reviewed snapshot must identify all foundation technologies")
    active = (await db.scalars(select(Technology).where(
        Technology.technology_code.in_(expected_codes), Technology.status == "ACTIVE",
    ).with_for_update())).all()
    actual = {item.technology_code: (item.id, item.revision) for item in active}
    if len(active) != len(expected_codes) or actual != expected_active_revisions:
        raise ValueError("active foundation revisions changed since the reviewed snapshot")
    existing = (await db.scalars(select(Technology).where(
        Technology.technology_code.in_(expected_codes), Technology.status.in_(("DRAFT", "REVIEW")),
    ))).all()
    if existing:
        raise ValueError("foundation draft or review revision already exists; do not replace it")
    for item in active:
        occupied = await db.scalar(select(Technology.id).where(
            Technology.technology_code == item.technology_code, Technology.revision == item.revision + 1,
        ))
        if occupied:
            raise ValueError("the next foundation revision number is already in use")
    gap_count = await db.scalar(select(func.count()).select_from(Module2MaterialGap))
    package = await apply_foundation_target_package(
        db, expected_existing=expected_existing_materials,
        expected_inventory_fingerprint=expected_material_fingerprint,
        acknowledge_test_data=acknowledge_test_data,
    )
    target_ids = [UUID(value) for value in package["target_ids"].values()]
    if len(target_ids) != len(targets()) or len(set(target_ids)) != len(target_ids):
        raise ValueError("foundation target package is incomplete or has duplicate identities")
    materials = (await db.scalars(select(Material).where(Material.id.in_(target_ids)).options(
        selectinload(Material.attributes)))).all()
    if len(materials) != len(target_ids):
        raise ValueError("foundation target materials could not be loaded")
    by_code = {}
    for material in materials:
        code = next((item.attribute_value for item in material.attributes if item.attribute_name == "registry_code"), None)
        if code:
            if code in by_code:
                raise ValueError("duplicate foundation registry code")
            by_code[code] = material
    totals = {"drafts": 0, "direct_links": 0, "legacy_unresolved": 0, "roles": 0,
              "reused_roles": 0, "rules": 0, "defaults": 0, "updated_defaults": 0,
              "unresolved": 0}
    for item in active:
        technology = await read_technology(db, item.id)
        if technology is None:
            raise ValueError("active foundation technology disappeared")
        draft, linked, unresolved = prepare_single_role_linkage_draft(
            technology, by_code, actor_role_code=actor_role_code)
        report = populate_blocked_foundation_draft(draft, by_code, actor_role_code=actor_role_code)
        if report["conflicts"]:
            raise ValueError(f"foundation draft has conflicting records: {technology.technology_code}")
        db.add(draft)
        totals["drafts"] += 1
        totals["direct_links"] += len(linked)
        totals["legacy_unresolved"] += len(unresolved)
        totals["roles"] += len(report["added_roles"])
        totals["reused_roles"] += len(report["reused_roles"])
        totals["rules"] += len(report["added_rules"])
        totals["defaults"] += report["added_defaults"]
        totals["updated_defaults"] += len(report["updated_defaults"])
        totals["unresolved"] += len(report["unresolved"])
    await db.flush()
    if totals["drafts"] != len(expected_codes):
        raise ValueError("foundation draft set is incomplete")
    if await db.scalar(select(func.count()).select_from(Module2MaterialGap)) != gap_count:
        raise ValueError("existing material gaps changed during preparation")
    return {"materials": {key: package[key] for key in ("created", "reused", "archived", "protected_materials")},
            "technology_drafts": totals, "existing_gaps": gap_count}
