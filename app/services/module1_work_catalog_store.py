"""Persistent backing for the existing M1 work catalog, preserving work_code."""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module1_work_item import ManualCalculationPriceRevision, WorkCatalogItem, WorkCatalogItemRevision
from app.models.module2_calculation_block import CalculationBlockTemplate, TechnologyCalculationBlock
from app.models.module2_technology import TechnologyWorkStep
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.services.audit_service import log_event
from app.services.module1_work_catalog import get_work_catalog_registry
from app.core.permission_guard import require_permission


async def load_work_catalog(db: AsyncSession):
    """Use persisted cards after migration; retain seed compatibility before it."""
    connection = await db.connection()
    available = await connection.run_sync(lambda sync: inspect(sync).has_table(WorkCatalogItem.__tablename__))
    if not available:
        return tuple(get_work_catalog_registry().works)
    items = tuple((await db.scalars(select(WorkCatalogItem).order_by(
        WorkCatalogItem.catalog_order, WorkCatalogItem.work_code))).all())
    if not items:
        return tuple(get_work_catalog_registry().works)
    return tuple(item for item in items if item.status != "ARCHIVED")


class WorkCatalogWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    work_code: str = Field(min_length=3, max_length=120)
    work_group: str = Field(min_length=1, max_length=120)
    work_category: str = Field(min_length=1, max_length=255)
    work_name: str = Field(min_length=1, max_length=500)
    default_unit: str = Field(min_length=1, max_length=50)
    allowed_units: list[str] = Field(min_length=1, max_length=30)
    is_range_allowed: bool = False
    applies_to: Literal["private_house", "apartment", "both"] = "both"
    description: str | None = None
    conditions: dict = Field(default_factory=dict)

    @field_validator("work_code")
    @classmethod
    def validate_code(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z][a-z0-9_]{2,119}", value):
            raise ValueError("work_code must be a stable lowercase catalog code")
        return value

    @model_validator(mode="after")
    def validate_catalog_references(self):
        registry = get_work_catalog_registry()
        groups = {group.work_group: group.work_category for group in registry.groups}
        if groups.get(self.work_group) != self.work_category:
            raise ValueError("work group and category must match the approved M1 catalog")
        if (self.default_unit not in registry.units or self.default_unit not in self.allowed_units or
                len(set(self.allowed_units)) != len(self.allowed_units) or
                any(unit not in registry.units for unit in self.allowed_units)):
            raise ValueError("work units must be approved catalog units and include the default")
        if not self.work_name.strip():
            raise ValueError("work name is required")
        return self


def _snapshot(item: WorkCatalogItem) -> dict:
    return {name: getattr(item, name) for name in (
        "work_code", "work_group", "work_category", "work_name", "default_unit", "allowed_units",
        "is_range_allowed", "applies_to", "module2_usage_hint", "module5_usage_hint", "description",
        "conditions", "catalog_order", "status", "version",
    )}


async def seed_existing_work_catalog(db: AsyncSession, *, actor_id: uuid.UUID | None = None) -> dict:
    """Import the approved baseline once; never overwrite a changed work item."""
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.m1.work.catalog.seed'))"))
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.m1.work.catalog.write'))"))
    existing = {item.work_code: item for item in (await db.scalars(select(WorkCatalogItem))).all()}
    created, reused, modified = 0, 0, []
    for position, work in enumerate(get_work_catalog_registry().works, start=1):
        source = asdict(work)
        source["allowed_units"] = list(source["allowed_units"])
        current = existing.get(work.work_code)
        if current is not None:
            # A later human edit is not overwritten. Its version remains authoritative.
            if current.version > 1:
                modified.append(current.work_code)
            elif any(getattr(current, key) != value for key, value in source.items()):
                raise ValueError(f"existing work identity differs from approved seed: {work.work_code}")
            if current.catalog_order == 0:
                current.catalog_order = position
            reused += 1
            continue
        item = WorkCatalogItem(**source, conditions={}, catalog_order=position, status="ACTIVE", version=1)
        db.add(item)
        revision = WorkCatalogItemRevision(id=uuid.uuid4(), work_code=work.work_code, version=1,
                                           snapshot={**source, "conditions": {}, "catalog_order": position, "status": "ACTIVE", "version": 1},
                                           created_by_user_id=actor_id)
        db.add(revision)
        created += 1
    await db.flush()
    return {"created": created, "reused": reused, "modified": tuple(modified)}


async def save_work_item(
    db: AsyncSession, payload: WorkCatalogWrite, *, actor_id: uuid.UUID | None,
    expected_version: int | None = None,
) -> WorkCatalogItem:
    """Create or revise a work card without a provider or price."""
    if db.bind.dialect.name == "postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('atom.m1.work.catalog.write'))"))
    item = await db.scalar(select(WorkCatalogItem).where(
        WorkCatalogItem.work_code == payload.work_code).with_for_update())
    name = " ".join(payload.work_name.split())
    duplicate = await db.scalar(select(WorkCatalogItem.work_code).where(
        WorkCatalogItem.work_code != payload.work_code, WorkCatalogItem.status != "ARCHIVED",
        func.lower(WorkCatalogItem.work_name) == name.lower(),
        WorkCatalogItem.default_unit == payload.default_unit,
        WorkCatalogItem.work_group == payload.work_group,
    ))
    if duplicate:
        raise ValueError("a work item with the same name, group and unit already exists")
    if item is None:
        if expected_version is not None:
            raise ValueError("work item no longer exists")
        order = (await db.scalar(select(func.max(WorkCatalogItem.catalog_order)))) or 0
        item = WorkCatalogItem(work_code=payload.work_code, status="DRAFT", version=1, catalog_order=order + 1)
        db.add(item)
    else:
        if expected_version is None or item.version != expected_version:
            raise ValueError("work item changed; refresh before saving")
        referenced = (await db.scalar(select(ProviderWorkCostOffer.id).where(
            ProviderWorkCostOffer.work_code == item.work_code).limit(1))) or (
            await db.scalar(select(TechnologyWorkStep.id).where(
                TechnologyWorkStep.work_code == item.work_code).limit(1))) or (
            await db.scalar(select(ManualCalculationPriceRevision.id).where(
                ManualCalculationPriceRevision.work_code == item.work_code).limit(1))) or (
            await db.scalar(select(TechnologyCalculationBlock.id).where(
                TechnologyCalculationBlock.work_code == item.work_code).limit(1))) or (
            await db.scalar(select(CalculationBlockTemplate.id).where(
                CalculationBlockTemplate.work_code == item.work_code).limit(1)))
        if referenced and (item.default_unit != payload.default_unit or item.conditions != payload.conditions):
            raise ValueError("unit or conditions cannot change while the work is referenced; create a new work")
        item.version += 1
    for key, value in payload.model_dump(exclude={"work_code"}).items():
        setattr(item, key, name if key == "work_name" else value)
    await db.flush()
    revision = WorkCatalogItemRevision(id=uuid.uuid4(), work_code=item.work_code, version=item.version,
                                       snapshot=_snapshot(item), created_by_user_id=actor_id)
    db.add(revision)
    await db.flush()
    await log_event(db, "M1_WORK_CATALOG_SAVED", "WorkCatalogItem", None, actor_id,
                    {"work_code": item.work_code, "version": item.version})
    return item


async def approve_work_item(db: AsyncSession, *, work_code: str, expected_version: int, actor: object) -> WorkCatalogItem:
    require_permission(actor, "MODULE_01_MATERIAL_HUB", "APPROVE")
    item = await db.scalar(select(WorkCatalogItem).where(WorkCatalogItem.work_code == work_code).with_for_update())
    if item is None or item.status != "DRAFT" or item.version != expected_version:
        raise ValueError("draft work changed or is unavailable")
    item.status = "ACTIVE"
    item.version += 1
    actor_id = getattr(actor, "id", None)
    revision = WorkCatalogItemRevision(id=uuid.uuid4(), work_code=item.work_code, version=item.version,
                                       snapshot=_snapshot(item), created_by_user_id=actor_id)
    db.add(revision)
    await db.flush()
    await log_event(db, "M1_WORK_CATALOG_APPROVED", "WorkCatalogItem", None, actor_id,
                    {"work_code": item.work_code, "version": item.version})
    return item
