from __future__ import annotations

from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DocumentStatus, MaterialStatus
from app.models.knowledge_resource import KnowledgeResource
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_document import MaterialDocument
from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_technology import Technology
from app.services.module1_work_catalog import get_work_item
from app.services.module2_content_catalog import category_tree, list_categories
from app.services.module2_technology_foundation import read_technology
from app.services.module2_workbench import format_consumption_norm


def _safe_source_url(value: str | None) -> str | None:
    if not value:
        return None
    parsed = urlsplit(value)
    return value if parsed.scheme in {"http", "https"} and parsed.netloc else None


async def public_catalog(db: AsyncSession, query: str = "") -> dict:
    rows = category_tree(await list_categories(db), public=True)
    categories = {row["category"].id: row["category"] for row in rows}
    if categories:
        result = await db.execute(
            select(Technology)
            .where(Technology.status == "ACTIVE", Technology.category_id.in_(categories))
            .order_by(Technology.technology_code, Technology.revision.desc())
        )
        latest = {}
        for item in result.scalars().all():
            latest.setdefault(item.technology_code, item)
    else:
        latest = {}
    needle = query.strip().casefold()
    technologies = tuple(
        sorted(
            (
                {"technology": item, "category": categories[item.category_id]}
                for item in latest.values()
                if not needle or needle in " ".join(
                    (item.name, item.technology_code, categories[item.category_id].name,
                     categories[item.category_id].code)
                ).casefold()
            ),
            key=lambda row: (row["category"].sort_order, row["technology"].name.casefold()),
        )
    )
    matched_rows = tuple(
        row for row in rows
        if not needle or needle in f"{row['category'].name} {row['category'].code}".casefold()
    )
    return {"categories": matched_rows, "technologies": technologies, "all_categories": rows}


async def public_category(db: AsyncSession, code: str) -> dict | None:
    catalog = await public_catalog(db)
    target = next(
        (row for row in catalog["all_categories"] if row["category"].code == code), None
    )
    if not target:
        return None
    category = target["category"]
    children = tuple(
        row for row in catalog["all_categories"]
        if row["category"].parent_id == category.id
    )
    technologies = tuple(
        row for row in catalog["technologies"]
        if row["technology"].category_id == category.id
    )
    by_id = {row["category"].id: row["category"] for row in catalog["all_categories"]}
    breadcrumb = []
    current = category
    while current:
        breadcrumb.append(current)
        current = by_id.get(current.parent_id)
    return {
        "category": category, "children": children,
        "technologies": technologies, "breadcrumb": tuple(reversed(breadcrumb)),
    }


async def public_technology(db: AsyncSession, code: str) -> Technology | None:
    catalog = await public_catalog(db)
    current = next(
        (row["technology"] for row in catalog["technologies"]
         if row["technology"].technology_code == code), None
    )
    return await read_technology(db, current.id) if current else None


async def technology_article(db: AsyncSession, technology: Technology) -> dict:
    category = await db.get(TechnologyCategory, technology.category_id)
    requirements = []
    for item in technology.requirements:
        label = item.material_role_code or "Требование к материалу"
        material = None
        if item.canonical_material_id:
            material = await db.get(Material, item.canonical_material_id)
            if material and material.status == MaterialStatus.VERIFIED:
                label = material.canonical_name
            else:
                material = None
                label = "Материал M1 недоступен для публикации"
        elif item.material_category_id:
            material_category = await db.get(MaterialCategory, item.material_category_id)
            if material_category and material_category.status == "ACTIVE":
                label = material_category.name
        requirements.append({"model": item, "label": label, "material": material})

    steps = []
    for item in sorted(technology.work_steps, key=lambda step: step.position):
        work = get_work_item(item.work_code)
        steps.append({"model": item, "work": work})

    evidence = []
    for item in technology.evidence_references:
        source = None
        if item.document_id:
            document = await db.get(MaterialDocument, item.document_id)
            if document and document.status == DocumentStatus.ACTIVE:
                source = {
                    "title": document.title,
                    "type": "Документ M1",
                    "url": _safe_source_url(document.source_url),
                }
        elif item.knowledge_resource_id:
            resource = await db.get(KnowledgeResource, item.knowledge_resource_id)
            if resource and resource.status in {"ACTIVE", "VERIFIED"}:
                source = {
                    "title": resource.title,
                    "type": "Ресурс M1",
                    "url": _safe_source_url(resource.source_url or resource.resource_url),
                }
        if source:
            evidence.append(source)

    def rule_text(rule) -> str | None:
        payload = rule.outcome_payload or {}
        for key in ("message", "description", "text", "note"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        return None

    warnings = tuple(
        text for rule in technology.knowledge_rules
        if rule.status == "ACTIVE" and rule.outcome_type in {"WARNING", "PROHIBITION"}
        if (text := rule_text(rule))
    )
    controls = tuple(
        text for rule in technology.knowledge_rules
        if rule.status == "ACTIVE" and rule.outcome_type in {"REQUIREMENT", "CONSTRAINT"}
        if (text := rule_text(rule))
    )
    return {
        "technology": technology,
        "category": category,
        "requirements": tuple(requirements),
        "layers": tuple(sorted(technology.layers, key=lambda layer: layer.position)),
        "steps": tuple(steps),
        "nodes": tuple(sorted(technology.nodes, key=lambda node: node.code)),
        "norms": tuple(
            format_consumption_norm(item) for item in technology.consumption_norms
            if item.status == "ACTIVE"
        ),
        "compatibility": tuple(
            item.reason for item in technology.compatibility_rules
            if item.status == "ACTIVE" and item.reason
        ),
        "warnings": warnings,
        "controls": controls,
        "evidence": tuple(evidence),
    }
