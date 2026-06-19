from collections import defaultdict
from decimal import Decimal

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import distinct, func, select

from app.api.deps import DBSession
from app.api.v1.material_hub_view import _format_datetime, _source_display_name
from app.models.enums import MaterialStatus
from app.models.material import Material
from app.models.material_category import MaterialCategory
from app.models.price_history import PriceHistory
from app.models.source import Source


router = APIRouter(prefix="/admin/price-dynamics/view", tags=["price-dynamics-view"])
templates = Jinja2Templates(directory="templates")


@router.get("", response_class=HTMLResponse)
async def price_dynamics_view(request: Request, db: DBSession):
    rows = await _load_price_rows(db)
    trend_rows = _build_trend_rows(rows)
    total_materials = await _count_active_materials(db)
    materials_with_history = await _count_materials_with_history(db)

    return templates.TemplateResponse(
        request,
        "price_dynamics_view.html",
        {
            "dt": _format_datetime,
            "source_display_name": _source_display_name,
            "price_points_total": len(rows),
            "materials_with_history": materials_with_history,
            "materials_without_history": max(total_materials - materials_with_history, 0),
            "trend_rows": trend_rows,
            "category_rows": _build_category_rows(trend_rows),
            "price_series": _build_price_series(rows),
        },
    )


async def _load_price_rows(db: DBSession) -> list[dict]:
    result = await db.execute(
        select(PriceHistory, Material, Source, MaterialCategory)
        .join(Material, PriceHistory.material_id == Material.id)
        .outerjoin(Source, PriceHistory.source_id == Source.id)
        .outerjoin(MaterialCategory, Material.category_id == MaterialCategory.id)
        .where(Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED]))
        .order_by(PriceHistory.material_id.asc(), PriceHistory.collected_at.desc())
        .limit(2000)
    )
    return [
        {
            "price": price,
            "material": material,
            "source": source,
            "category": category,
        }
        for price, material, source, category in result.all()
    ]


async def _count_active_materials(db: DBSession) -> int:
    result = await db.execute(
        select(func.count(Material.id)).where(
            Material.status.not_in([MaterialStatus.ARCHIVED, MaterialStatus.REJECTED])
        )
    )
    return result.scalar() or 0


async def _count_materials_with_history(db: DBSession) -> int:
    result = await db.execute(select(func.count(distinct(PriceHistory.material_id))))
    return result.scalar() or 0


def _build_trend_rows(rows: list[dict]) -> list[dict]:
    by_material: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        by_material[str(row["material"].id)].append(row)

    trend_rows: list[dict] = []
    for material_rows in by_material.values():
        sorted_rows = sorted(
            material_rows,
            key=lambda item: item["price"].collected_at,
            reverse=True,
        )
        latest = sorted_rows[0]
        previous = sorted_rows[1] if len(sorted_rows) > 1 else None
        latest_price = latest["price"].price
        previous_price = previous["price"].price if previous else None
        diff = latest_price - previous_price if previous_price is not None else None
        percent = _percent_change(latest_price, previous_price)

        trend_rows.append({
            "material": latest["material"],
            "category": latest["category"],
            "source": latest["source"],
            "latest": latest["price"],
            "previous": previous["price"] if previous else None,
            "diff": diff,
            "percent": percent,
        })

    return sorted(
        trend_rows,
        key=lambda item: item["latest"].collected_at,
        reverse=True,
    )


def _build_category_rows(trend_rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in trend_rows:
        category_name = row["category"].name if row["category"] else "Категория не указана"
        grouped[category_name].append(row)

    category_rows: list[dict] = []
    for category_name, rows in grouped.items():
        percents = [row["percent"] for row in rows if row["percent"] is not None]
        avg_percent = sum(percents, Decimal("0")) / len(percents) if percents else None
        category_rows.append({
            "category": category_name,
            "materials_total": len(rows),
            "materials_with_change": len(percents),
            "avg_percent": avg_percent,
        })
    return sorted(category_rows, key=lambda item: item["category"])


def _build_price_series(rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["material"].id)].append(row)

    series: list[dict] = []
    for material_id, material_rows in grouped.items():
        if len(material_rows) < 2:
            continue
        sorted_rows = sorted(material_rows, key=lambda item: item["price"].collected_at)
        material = sorted_rows[-1]["material"]
        category = sorted_rows[-1]["category"]
        source = sorted_rows[-1]["source"]
        points = [
            {
                "date": _format_datetime(item["price"].collected_at),
                "price": float(item["price"].price),
                "currency": item["price"].currency,
            }
            for item in sorted_rows
        ]
        series.append({
            "material_id": material_id,
            "name": material.canonical_name,
            "category": category.name if category else "",
            "manufacturer": material.manufacturer or "",
            "region": sorted_rows[-1]["price"].region or "",
            "source": _source_display_name(source),
            "points": points,
        })

    return sorted(series, key=lambda item: item["name"])[:100]


def _percent_change(latest_price: Decimal, previous_price: Decimal | None) -> Decimal | None:
    if previous_price in (None, 0, Decimal("0")):
        return None
    return ((latest_price - previous_price) / previous_price * Decimal("100")).quantize(Decimal("0.01"))
