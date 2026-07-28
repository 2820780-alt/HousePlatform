from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.api.v1 import api_router
from app.api.v1.admin_users_roles_view import ui_router as admin_users_roles_ui_router
from app.config import settings
from app.core.browser_auth import browser_auth_redirect_middleware
from app.database import close_db, init_db
from app.services.module1_ref4_normalization_policy import require_module1_ref45_runtime
from app.services.module1_ref6_work_material_policy import require_module1_ref6_runtime
from app.services.module1_ref_runtime_artifacts import validate_configured_module1_ref_runtime


@asynccontextmanager
async def lifespan(app: FastAPI):
    ref_validation = validate_configured_module1_ref_runtime()
    app.state.module1_ref_runtime = ref_validation
    app.state.module1_ref_artifact_validation = ref_validation.as_dict()
    ref45_validation = require_module1_ref45_runtime()
    app.state.module1_ref45_runtime = ref45_validation
    app.state.module1_ref45_validation = ref45_validation.as_dict()
    ref6_validation = require_module1_ref6_runtime()
    app.state.module1_ref6_runtime = ref6_validation
    app.state.module1_ref6_validation = ref6_validation.as_dict()
    await init_db()
    try:
        yield
    finally:
        await close_db()


app = FastAPI(
    title="Атом API",
    version="1.0.0",
    debug=settings.APP_DEBUG,
    lifespan=lifespan,
)


app.middleware("http")(browser_auth_redirect_middleware)

@app.get("/api/v1/health", tags=["system"])
async def health_check():
    return {
        "status": "ok",
        "version": "Master_Prompt_v1.1",
        "environment": settings.APP_ENV,
    }


@app.get("/api", include_in_schema=False, response_class=HTMLResponse)
@app.get("/api/", include_in_schema=False, response_class=HTMLResponse)
async def api_entrypoint():
    return """
    <!doctype html>
    <html lang="ru">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>АТОМ API</title>
        <style>
          body {
            margin: 0;
            min-height: 100vh;
            display: grid;
            place-items: center;
            color: #eef7ff;
            font-family: Arial, Helvetica, sans-serif;
            background: linear-gradient(135deg, #050917, #0b1434 55%, #130d29);
          }
          main {
            width: min(620px, calc(100vw - 32px));
            padding: 24px;
            border: 1px solid rgba(119, 172, 255, 0.22);
            border-radius: 10px;
            background: rgba(10, 18, 43, 0.86);
            box-shadow: 0 22px 70px rgba(0, 0, 0, 0.38);
          }
          h1 { margin: 0 0 8px; letter-spacing: 0; }
          p { color: #8fa4c8; line-height: 1.5; }
          a {
            display: inline-flex;
            margin: 8px 8px 0 0;
            padding: 9px 12px;
            border: 1px solid rgba(24, 215, 242, 0.38);
            border-radius: 8px;
            color: #eef7ff;
            text-decoration: none;
            background: rgba(24, 215, 242, 0.1);
            font-weight: 700;
          }
        </style>
      </head>
      <body>
        <main>
          <h1>АТОМ API</h1>
          <p>/api — обзорная точка входа. Рабочий API живет под /api/v1, документация доступна через Swagger.</p>
          <a href="/docs">Открыть Swagger</a>
          <a href="/api/v1/health">Health check</a>
          <a href="/api/v1/admin/cabinet/view">Dashboard</a>
        </main>
      </body>
    </html>
    """


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


def _redirect_to_module3_api_path(path: str = "", query_string: str = "") -> RedirectResponse:
    suffix = f"/{path}" if path else ""
    query = f"?{query_string}" if query_string else ""
    return RedirectResponse(
        url=f"/api/v1/admin/users-roles/view{suffix}{query}",
        status_code=307,
    )


@app.get("/admin/users-roles/view", tags=["module-compatibility"], include_in_schema=False)
async def legacy_users_roles_view_route(request: Request):
    return _redirect_to_module3_api_path(query_string=request.url.query)


@app.get("/admin/users-roles/view/{path:path}", tags=["module-compatibility"], include_in_schema=False)
async def legacy_users_roles_view_nested_route(path: str, request: Request):
    return _redirect_to_module3_api_path(path=path, query_string=request.url.query)


app.include_router(admin_users_roles_ui_router)
app.include_router(api_router, prefix="/api/v1")
