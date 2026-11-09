from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permission_guard import require_permission
from app.models.module2_technology import MODULE2_OWNER_CODE, Technology
from app.schemas.module2_technology import TechnologyLifecycle
from app.services.dashboard_widget_payload import build_atom_widget_payload
from app.services.module2_technology_foundation import validate_technology_activation


TECHNOLOGY_READINESS_WIDGET_CODE = "MODULE_02_TECHNOLOGY_READINESS_WIDGET"


async def build_technology_readiness_widget(
    db: AsyncSession,
    user,
) -> dict:
    require_permission(user, MODULE2_OWNER_CODE, "VIEW")
    result = await db.execute(
        select(Technology).options(selectinload(Technology.layers))
    )
    technologies = list(result.scalars().unique().all())
    statuses = {status.value: 0 for status in TechnologyLifecycle}
    blocked = 0
    for technology in technologies:
        statuses[technology.status] = statuses.get(technology.status, 0) + 1
        if validate_technology_activation(technology):
            blocked += 1

    latest_update = max(
        (technology.updated_at for technology in technologies if technology.updated_at),
        default=None,
    )
    items = [
        {
            "label": status.value,
            "value": statuses[status.value],
            "status": "attention" if status == TechnologyLifecycle.REVIEW else "info",
        }
        for status in TechnologyLifecycle
    ]
    return build_atom_widget_payload(
        widget_code=TECHNOLOGY_READINESS_WIDGET_CODE,
        source_module_code=MODULE2_OWNER_CODE,
        feature_code="TECHNOLOGY_CONSTRUCTION_GROUPS",
        title="Готовность базы технологий",
        status="attention" if blocked else "ok",
        style_variant="operational",
        icon_key="workflow",
        empty_state_label="Редакции технологий пока не созданы.",
        primary_value=len(technologies),
        primary_label="Редакций технологий",
        secondary_value=blocked,
        secondary_label="С блокирующими причинами",
        items=items,
        cta={"label": "Открыть модуль", "route": "/api/v1/module2"},
        updated_at=latest_update,
    ).to_dict()
