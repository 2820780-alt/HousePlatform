from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import RedirectResponse

from app.api.v1 import api_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Атом API",
    version="1.0.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)


@app.get("/api/v1/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "version": "Master_Prompt_v1.1",
        "environment": settings.APP_ENV,
    }


@app.get("/modules/price-history", tags=["module-compatibility"], include_in_schema=False)
async def legacy_price_history_route():
    return RedirectResponse(url="/api/v1/admin/price-dynamics/view", status_code=307)


@app.get("/modules/analytics", tags=["module-compatibility"], include_in_schema=False)
async def legacy_analytics_route(section: str | None = None):
    target = (
        "/api/v1/admin/price-dynamics/view"
        if section == "price-dynamics"
        else "/api/v1/admin/cabinet/view/modules/11"
    )
    return RedirectResponse(url=target, status_code=307)


@app.get("/modules/digital-object", tags=["module-compatibility"], include_in_schema=False)
async def legacy_digital_object_route():
    return RedirectResponse(url="/modules/digital-house", status_code=307)


@app.get("/modules/digital-house", tags=["module-compatibility"], include_in_schema=False)
async def digital_house_placeholder_route():
    return RedirectResponse(url="/api/v1/admin/cabinet/view/modules/7", status_code=307)


@app.get("/modules/constructor-lite", tags=["module-compatibility"], include_in_schema=False)
async def constructor_lite_placeholder_route():
    return RedirectResponse(url="/api/v1/admin/cabinet/view", status_code=307)


@app.get("/modules/construction-groups", tags=["module-compatibility"], include_in_schema=False)
async def legacy_construction_groups_route():
    return RedirectResponse(
        url="/api/v1/admin/material-hub/view?feature=construction-applicability",
        status_code=307,
    )


app.include_router(api_router, prefix="/api/v1")
