from fastapi import APIRouter

from app.api.deps import CurrentUser, DBSession
from app.schemas.module_visibility import ModuleVisibilityItem
from app.services.module_visibility import get_visible_modules_for_user


router = APIRouter(prefix="/access", tags=["access"])


@router.get("/my-modules", response_model=list[ModuleVisibilityItem])
async def get_my_modules(db: DBSession, user: CurrentUser):
    return await get_visible_modules_for_user(db, user)
