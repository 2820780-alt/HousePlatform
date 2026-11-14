from __future__ import annotations

import uuid
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import DocumentStatus, MaterialStatus
from app.models.knowledge_resource import KnowledgeResource
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.material_document import MaterialDocument
from app.models.module2_content_catalog import TechnologyCategory
from app.models.module2_technology import Technology, TechnologyMaterialRequirement, TechnologyNode
from app.services.module2_content_catalog import category_tree, list_categories
from app.services.module2_default_assumptions import active_defaults, requires_explicit_foundation_input
from app.services.module2_encyclopedia_editorial import (
    MATERIAL_NAMES, MATERIAL_REQUIREMENT_TITLES, WORK_STEP_GUIDANCE, category_article,
    effective_material_name, material_default_label,
)
from app.services.module2_material_resolution import (
    compatible_materials, gap_for_requirement, material_card_url,
)
from app.services.module2_foundation_comparison import foundation_comparison
from app.services.module2_technology_foundation import read_technology
from app.services.module2_workbench import LAYER_NAMES, REQUIREMENT_NAMES, format_consumption_norm


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


async def public_category(db: AsyncSession, code: str, *, compare_codes: list[str] | None = None,
                          scenario: str = "") -> dict | None:
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
    public_by_id = {row["technology"].id: row for row in catalog["technologies"]}
    related = []
    if public_by_id:
        nodes = (await db.scalars(select(TechnologyNode).where(
            TechnologyNode.technology_id.in_(public_by_id),
            TechnologyNode.node_type == "RELATED_CATEGORY",
        ))).all()
        related = [
            {**public_by_id[node.technology_id], "relationship_name": node.name,
             "relationship_description": node.description.replace(code, f"разделу «{category.name}»")
             if node.description else None}
            for node in nodes
            if (node.conditions or {}).get("category_code") == code
            and public_by_id[node.technology_id]["technology"].category_id != category.id
        ]
    related_technologies = tuple({row["technology"].id: row for row in related}.values())
    by_id = {row["category"].id: row["category"] for row in catalog["all_categories"]}
    breadcrumb = []
    current = category
    while current:
        breadcrumb.append(current)
        current = by_id.get(current.parent_id)
    overview = category_article(code)
    comparison = tuple(
        {"category": row["category"], "article": category_article(row["category"].code)}
        for row in children
        if category_article(row["category"].code)
    ) if code == "FOUNDATIONS" else tuple(
        {"category": row["category"], "note": note}
        for target_code, note in (overview or {}).get("comparison", ())
        for row in catalog["all_categories"] if row["category"].code == target_code
    )
    materials = ()
    if technologies:
        requirements = (await db.scalars(select(TechnologyMaterialRequirement).where(
            TechnologyMaterialRequirement.technology_id.in_(
                row["technology"].id for row in technologies
            ),
        ))).all()
        materials = tuple(dict.fromkeys(
            MATERIAL_NAMES.get(item.code, REQUIREMENT_NAMES.get(item.code, item.code))
            for item in requirements
        ))
    return {
        "category": category, "children": children,
        "technologies": technologies, "related_technologies": related_technologies,
        "breadcrumb": tuple(reversed(breadcrumb)),
        "overview": overview, "comparison": comparison, "materials": materials,
        "foundation_compare": foundation_comparison(catalog["technologies"], compare_codes or [], scenario)
        if code == "FOUNDATIONS" else None,
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
    evidence = []
    evidence_by_target = {}
    seen_sources = set()
    sources_by_key = {}
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
            key = (source["type"], source["title"], source["url"])
            source = sources_by_key.setdefault(key, source)
            if key not in seen_sources:
                evidence.append(source)
                seen_sources.add(key)
            evidence_by_target.setdefault((item.target_kind, item.target_reference), []).append(source)

    for number, source in enumerate(evidence, start=1):
        source["number"] = number

    assumptions = active_defaults(technology)
    requirements = []
    for item in technology.requirements:
        label = REQUIREMENT_NAMES.get(item.code, item.code)
        candidates = await compatible_materials(db, item)
        material = candidates[0] if candidates else None
        gap = await gap_for_requirement(db, item.id) if not candidates else None
        linked_defaults = tuple(
            assumption for assumption in assumptions if assumption.material_requirement_id == item.id
        )
        default_label = material_default_label(linked_defaults)
        display_name = effective_material_name(item.code, label, linked_defaults)
        requirements.append({
            "model": item, "label": label, "display_name": display_name,
            "base_name": MATERIAL_NAMES.get(item.code, label), "material": material,
            "requirement_title": MATERIAL_REQUIREMENT_TITLES.get(item.code, "Требование к материалу"),
            "candidates": candidates, "gap": gap, "default_label": default_label,
            "sources": tuple(evidence_by_target.get(("MATERIAL_REQUIREMENT", str(item.id)), ())),
        })

    from app.services.module1_work_catalog_store import load_work_catalog
    work_by_code = {item.work_code: item for item in await load_work_catalog(db)}
    steps = []
    for item in sorted(technology.work_steps, key=lambda step: step.position):
        work = work_by_code.get(item.work_code)
        guidance = WORK_STEP_GUIDANCE.get(item.work_code)
        steps.append({
            "model": item, "work": work,
            "purpose": guidance[0] if guidance else None,
            "check": guidance[1] if guidance else None,
            "materials": tuple(
                requirement for requirement in requirements
                if guidance and requirement["model"].code in guidance[2]
            ),
            "sources": tuple(evidence_by_target.get(("WORK_STEP", str(item.id)), ())),
        })

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
    editorial = {}
    for rule in technology.knowledge_rules:
        if rule.status != "ACTIVE" or rule.outcome_type != "INFORMATION":
            continue
        section = (rule.outcome_payload or {}).get("section")
        message = rule_text(rule)
        if section and message:
            editorial.setdefault(section, []).append({
                "text": message,
                "sources": tuple(evidence_by_target.get(("KNOWLEDGE_RULE", str(rule.id)), ())),
            })

    catalog = await public_catalog(db)
    categories_by_id = {row["category"].id: row["category"] for row in catalog["all_categories"]}
    breadcrumb = []
    current_category = category
    while current_category:
        breadcrumb.append(current_category)
        current_category = categories_by_id.get(current_category.parent_id)
    categories_by_code = {
        row["category"].code: row["category"] for row in catalog["all_categories"]
    }
    technologies_by_code = {
        row["technology"].technology_code: row["technology"]
        for row in catalog["technologies"]
    }
    related_categories = tuple({category.id: category for node in technology.nodes
        if node.node_type == "RELATED_CATEGORY"
        if (code := (node.conditions or {}).get("category_code")) in categories_by_code
        if (category := categories_by_code[code])}.values())
    related_technologies = tuple({related.id: related for node in technology.nodes
        if node.node_type == "RELATED_TECHNOLOGY"
        if (code := (node.conditions or {}).get("technology_code")) in technologies_by_code
        if (related := technologies_by_code[code])}.values())
    family_alternatives = tuple(
        row["technology"] for row in catalog["technologies"]
        if row["technology"].category_id == technology.category_id
        and row["technology"].technology_code != technology.technology_code
    )
    defaults = []
    for item in assumptions:
        if requires_explicit_foundation_input(technology, item):
            defaults.append({
                "name": item.name_ru, "value": "Уточняется для объекта", "unit": None,
                "warning": "Требуется значение объекта или выбранной системы.",
                "action": None, "range": False, "alternatives": (),
            })
            continue
        defaults.append({
            "name": item.name_ru, "value": await _default_label(db, item),
            "unit": item.unit, "warning": item.warning_text,
            "action": _default_action(item.parameter_code),
            "range": item.value_type == "NUMBER",
            "alternatives": await _default_alternatives(db, item),
        })
    return {
        "technology": technology,
        "category": category,
        "breadcrumb": tuple(reversed(breadcrumb)),
        "requirements": tuple(requirements),
        "layers": tuple({"model": layer, "label": LAYER_NAMES.get(layer.functional_role, layer.functional_role)}
                        for layer in sorted(technology.layers, key=lambda layer: layer.position)),
        "steps": tuple(steps),
        "defaults": tuple(defaults),
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
        "editorial": {key: tuple(value) for key, value in editorial.items()},
        "family_alternatives": family_alternatives,
        "related_categories": related_categories,
        "related_technologies": related_technologies,
        "evidence": tuple(evidence),
        "material_card_url": material_card_url,
    }


async def _default_label(db: AsyncSession, assumption) -> str:
    value = assumption.default_value.get("value")
    if assumption.value_type == "MATERIAL_CLASS":
        category = await db.get(MaterialCategory, uuid.UUID(str(value)))
        return category.name if category else "Класс M1 недоступен"
    if assumption.value_type == "MATERIAL":
        material = await db.get(Material, uuid.UUID(str(value)))
        return material.canonical_name if material else "Материал M1 недоступен"
    if assumption.value_type == "BOOLEAN":
        return "Да" if value else "Нет"
    return str(value)


def _default_action(parameter_code: str) -> str:
    if "CONCRETE" in parameter_code:
        return "Выбрать другой бетон"
    if "REBAR" in parameter_code:
        return "Выбрать другую арматуру"
    if "DEPTH" in parameter_code:
        return "Изменить глубину"
    if "WATERPROOF" in parameter_code or "MEMBRANE" in parameter_code:
        return "Выбрать другую гидроизоляцию"
    return "Посмотреть варианты"


async def _default_alternatives(db: AsyncSession, assumption) -> tuple[str, ...]:
    allowed = assumption.allowed_values or {}
    if assumption.value_type == "ENUM":
        return tuple(str(value) for value in allowed.get("values", ()))
    if assumption.value_type == "MATERIAL_CLASS":
        values = []
        for value in allowed.get("category_ids", ()):
            category = await db.get(MaterialCategory, uuid.UUID(str(value)))
            if category:
                values.append(category.name)
        return tuple(values)
    if assumption.value_type == "MATERIAL":
        values = []
        for value in allowed.get("material_ids", ()):
            material = await db.get(Material, uuid.UUID(str(value)))
            if material and material.status == MaterialStatus.VERIFIED:
                values.append(material.canonical_name)
        return tuple(values)
    if assumption.value_type == "NUMBER" and "min" in allowed and "max" in allowed:
        return (f"{allowed['min']}–{allowed['max']} {assumption.unit or ''}".strip(),)
    return ()
