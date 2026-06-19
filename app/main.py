from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1 import api_router
from app.config import settings
from app.database import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="HousePlatform API",
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


app.include_router(api_router, prefix="/api/v1")
