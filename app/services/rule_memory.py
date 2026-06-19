from __future__ import annotations

import json
import re
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog_product import CatalogProduct
from app.models.material import Material
from app.models.rule_memory import RuleMemory


def normalize_rule_pattern(value: str | None) -> str:
    text = (value or "").lower().replace("ё", "е")
    text = re.sub(r"[^0-9a-zа-я]+", " ", text, flags=re.IGNORECASE)
    return " ".join(text.split())


def build_rule_patterns(*values: str | None) -> list[str]:
    patterns: list[str] = []
    for value in values:
        normalized = normalize_rule_pattern(value)
        if normalized and normalized not in patterns:
            patterns.append(normalized)
        compact = _compact_pattern(normalized)
        if compact and compact not in patterns:
            patterns.append(compact)
    return patterns


async def remember_material_rule(
    db: AsyncSession,
    material: Material,
    patterns: list[str],
    source: str = "admin_edit",
    attributes: dict | None = None,
) -> None:
    for pattern in patterns:
        normalized = normalize_rule_pattern(pattern)
        if len(normalized) < 3:
            continue
        result = await db.execute(
            select(RuleMemory).where(
                RuleMemory.normalized_pattern == normalized,
                RuleMemory.material_id == material.id,
            )
        )
        rule = result.scalar_one_or_none()
        if rule:
            rule.category_id = material.subcategory_id or material.category_id
            rule.attributes_json = json.dumps(attributes or {}, ensure_ascii=False)
            rule.confirmed_count += 1
            rule.confidence_boost = rule.get_confidence_boost()
            db.add(rule)
            continue
        db.add(
            RuleMemory(
                normalized_pattern=normalized,
                material_id=material.id,
                category_id=material.subcategory_id or material.category_id,
                attributes_json=json.dumps(attributes or {}, ensure_ascii=False),
                confidence_boost=Decimal("0.10"),
                confirmed_count=1,
                source=source,
            )
        )
    await db.flush()


async def find_rule_for_product(
    db: AsyncSession,
    product: CatalogProduct,
    allowed_category_ids: set[UUID] | None = None,
) -> RuleMemory | None:
    product_patterns = build_rule_patterns(product.raw_name, product.normalized_name, product.raw_category)
    if not product_patterns:
        return None
    result = await db.execute(
        select(RuleMemory)
        .options(selectinload(RuleMemory.material))
        .order_by(RuleMemory.confirmed_count.desc(), RuleMemory.updated_at.desc())
    )
    rules = list(result.scalars().all())
    for rule in rules:
        if allowed_category_ids is not None and rule.category_id and rule.category_id not in allowed_category_ids:
            continue
        rule_pattern = normalize_rule_pattern(rule.normalized_pattern)
        if not rule_pattern:
            continue
        if any(_pattern_matches(rule_pattern, product_pattern) for product_pattern in product_patterns):
            return rule
    return None


def _compact_pattern(value: str) -> str:
    if not value:
        return ""
    stopwords = {
        "в",
        "для",
        "и",
        "из",
        "на",
        "по",
        "с",
        "со",
        "шт",
        "мм",
        "м",
        "руб",
    }
    tokens = [token for token in value.split() if token not in stopwords]
    return " ".join(tokens[:8])


def _pattern_matches(rule_pattern: str, product_pattern: str) -> bool:
    if rule_pattern == product_pattern:
        return True
    if len(rule_pattern) >= 8 and rule_pattern in product_pattern:
        return True
    rule_tokens = set(rule_pattern.split())
    product_tokens = set(product_pattern.split())
    if not rule_tokens:
        return False
    common = rule_tokens.intersection(product_tokens)
    return len(common) >= min(3, len(rule_tokens))
