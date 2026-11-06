from __future__ import annotations

import re
from collections import defaultdict
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_technology import Technology


CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


class ContentCatalogError(ValueError):
    pass


def _code(value: str, *, field: str = "code") -> str:
    code = value.strip().upper()
    if not CODE_PATTERN.fullmatch(code) or len(code) > 120:
        raise ContentCatalogError(f"{field} must be a stable uppercase ASCII code")
    return code


async def list_categories(db: AsyncSession) -> tuple[TechnologyCategory, ...]:
    result = await db.execute(select(TechnologyCategory))
    return tuple(result.scalars().all())


async def resolve_category_id(db: AsyncSession, code: str | None) -> UUID | None:
    if not code:
        return None
    category = await db.scalar(
        select(TechnologyCategory).where(TechnologyCategory.code == _code(code))
    )
    if not category or category.status == "ARCHIVED":
        raise ContentCatalogError("category is unavailable")
    return category.id


def category_tree(
    categories: tuple[TechnologyCategory, ...], *, public: bool = False
) -> tuple[dict, ...]:
    by_id = {item.id: item for item in categories}
    children: dict[UUID | None, list[TechnologyCategory]] = defaultdict(list)
    for item in categories:
        children[item.parent_id].append(item)
    for siblings in children.values():
        siblings.sort(key=lambda item: (item.sort_order, item.name.casefold(), item.code))

    rows: list[dict] = []
    visited: set[UUID] = set()

    def visit(item: TechnologyCategory, depth: int, ancestors_active: bool) -> None:
        if item.id in visited:
            return
        visited.add(item.id)
        active = ancestors_active and item.status == "ACTIVE"
        if not public or active:
            rows.append({"category": item, "depth": depth, "active": active})
        for child in children.get(item.id, ()):
            visit(child, depth + 1, active)

    for root in children.get(None, ()):
        visit(root, 0, True)
    if not public:
        for item in categories:
            if item.id not in visited:
                visit(item, 0, False)
    return tuple(rows)


async def create_category(
    db: AsyncSession, *, code: str, name: str, parent_code: str | None,
    sort_order: int = 0, scope_code: str = "RESIDENTIAL", description: str | None = None,
) -> TechnologyCategory:
    code = _code(code)
    scope_code = _code(scope_code, field="scope_code")
    name = name.strip()
    if not name or len(name) > 255 or sort_order < 0:
        raise ContentCatalogError("category name or sort order is invalid")
    if await db.scalar(select(TechnologyCategory.id).where(TechnologyCategory.code == code)):
        raise ContentCatalogError("category code already exists")
    parent = await _parent_by_code(db, parent_code)
    category = TechnologyCategory(
        code=code, name=name, description=description or None,
        parent_id=parent.id if parent else None, sort_order=sort_order,
        scope_code=scope_code, status="DRAFT", content_status="EMPTY",
    )
    db.add(category)
    await db.flush()
    return category


async def update_draft_category(
    db: AsyncSession, category: TechnologyCategory, *, name: str,
    parent_code: str | None, sort_order: int, scope_code: str,
    description: str | None = None,
) -> TechnologyCategory:
    if category.status != "DRAFT":
        raise ContentCatalogError("only DRAFT categories can be edited")
    name = name.strip()
    if not name or len(name) > 255 or sort_order < 0:
        raise ContentCatalogError("category name or sort order is invalid")
    parent = await _parent_by_code(db, parent_code)
    if parent:
        if parent.id == category.id:
            raise ContentCatalogError("category cannot be its own parent")
        by_id = {item.id: item for item in await list_categories(db)}
        ancestor = parent
        seen: set[UUID] = set()
        while ancestor:
            if ancestor.id == category.id or ancestor.id in seen:
                raise ContentCatalogError("category hierarchy cannot contain a cycle")
            seen.add(ancestor.id)
            ancestor = by_id.get(ancestor.parent_id)
    category.name = name
    category.description = description or None
    category.parent_id = parent.id if parent else None
    category.sort_order = sort_order
    category.scope_code = _code(scope_code, field="scope_code")
    await db.flush()
    return category


async def transition_category(
    db: AsyncSession, category: TechnologyCategory, target: str
) -> TechnologyCategory:
    if target == "ACTIVE" and category.status == "DRAFT":
        if category.parent_id:
            parent = await db.get(TechnologyCategory, category.parent_id)
            if not parent or parent.status != "ACTIVE":
                raise ContentCatalogError("parent category must be ACTIVE")
    elif target == "ARCHIVED" and category.status in {"DRAFT", "ACTIVE"}:
        active_children = await db.scalar(
            select(func.count()).select_from(TechnologyCategory).where(
                TechnologyCategory.parent_id == category.id,
                TechnologyCategory.status == "ACTIVE",
            )
        )
        active_technologies = await db.scalar(
            select(func.count()).select_from(Technology).where(
                Technology.category_id == category.id, Technology.status == "ACTIVE"
            )
        )
        if active_children or active_technologies:
            raise ContentCatalogError("archive active children and technologies first")
    else:
        raise ContentCatalogError("unsupported category lifecycle transition")
    category.status = target
    await db.flush()
    return category


async def start_content_package(db: AsyncSession, category: TechnologyCategory) -> None:
    if category.status != "ACTIVE" or category.content_status != "EMPTY":
        raise ContentCatalogError("content package requires an ACTIVE empty category")
    category.content_status = "IN_PROGRESS"
    await db.flush()


async def _parent_by_code(
    db: AsyncSession, parent_code: str | None
) -> TechnologyCategory | None:
    if not parent_code:
        return None
    parent = await db.scalar(
        select(TechnologyCategory).where(TechnologyCategory.code == _code(parent_code))
    )
    if not parent or parent.status == "ARCHIVED":
        raise ContentCatalogError("parent category is unavailable")
    return parent
