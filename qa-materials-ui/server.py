"""Run an isolated, local-only materials UI test server against the QA database."""

import os
from pathlib import Path
import sys
from fastapi import Depends
from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import selectinload

QA_DATABASE = "houseplatform_fnd_m1_m2_20261110"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=QA_DATABASE).render_as_string(hide_password=False)
os.environ["APP_DEBUG"] = "false"
os.environ["REDIS_URL"] = "redis://127.0.0.1:1/0"
os.environ["MODULE1_REF_RUNTIME_MODE"] = "legacy"
os.environ["MODULE1_REF45_MODE"] = "legacy"
os.environ["MODULE1_REF6_MODE"] = "legacy"

from app.config import settings

if make_url(settings.DATABASE_URL).database != QA_DATABASE:
    raise RuntimeError("Refusing to run UI QA outside its isolated database")

from app.api.deps import get_current_user
from app.database import get_db
from app.main import app
from app.models.enums import UserRole, UserStatus
from app.models.user import User
from app.models.user_role_assignment import UserRoleAssignment


async def qa_admin(db=Depends(get_db)):
    user = await db.scalar(
        select(User).where(User.role == UserRole.ADMIN, User.status == UserStatus.ACTIVE)
        .options(selectinload(User.role_assignments).selectinload(UserRoleAssignment.role),
                 selectinload(User.workspace_members), selectinload(User.module_access))
        .order_by(User.id).limit(1)
    )
    if user is None:
        raise RuntimeError("QA database must contain an active administrator")
    return user


app.dependency_overrides[get_current_user] = qa_admin

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
