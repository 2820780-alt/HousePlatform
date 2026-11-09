from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from app.api.deps import CurrentUser, DBSession
from app.core.access_scopes import AccessScope
from app.core.permission_guard import require_permission
from app.models.module2_technology import MODULE2_OWNER_CODE
from app.services.module2_content_catalog import list_categories
from app.services.module2_home import ZONE_GROUPS, home_zones
from app.services.module2_workbench import workbench_permissions


router = APIRouter(prefix="/module2", tags=["module2-home"])
templates = Jinja2Templates(directory="templates")
ASSET_DIR = Path(__file__).resolve().parents[2] / "assets" / "module2_home"


@router.get("", response_class=HTMLResponse)
async def module2_home(request: Request, db: DBSession, user: CurrentUser):
    require_permission(user, MODULE2_OWNER_CODE, "VIEW", scope=AccessScope.LIMITED)
    zones = home_zones(await list_categories(db))
    by_part = {item["part"]: item for item in zones}
    requested_part = request.query_params.get("part", "foundations")
    selected = by_part.get(requested_part, by_part["foundations"])
    requested_view = request.query_params.get("view", "cutaway")
    house_view = requested_view if requested_view in {"cutaway", "exterior"} else "cutaway"
    return templates.TemplateResponse(request, "module2_home.html", {
        "zones": zones, "zone_groups": ZONE_GROUPS, "zones_by_part": by_part,
        "selected": selected, "house_view": house_view,
        "can_workbench": workbench_permissions(user)["edit"],
        "m2_nav_active": "home", "atom_topbar_current_block": "Модуль №2: Технологии",
    })


@router.get("/home-assets/{name}", include_in_schema=False)
async def module2_home_asset(name: str):
    if name not in {"cutaway", "exterior"}:
        raise HTTPException(status_code=404)
    return FileResponse(ASSET_DIR / f"{name}.svg", media_type="image/svg+xml")
