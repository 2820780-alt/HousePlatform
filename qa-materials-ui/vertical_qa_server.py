"""Local-only UI QA for the restored vertical database, never production."""
import os
import sys
from pathlib import Path
from types import SimpleNamespace

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

QA_DATABASE = "houseplatform_vertical_20261113_171244"
original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    return original_init(self, *args, **kwargs)


BaseSettings.__init__ = no_env_file
for key in ("DATABASE_URL", "DATABASE_URL_SYNC"):
    if key in os.environ:
        os.environ[key] = make_url(os.environ[key]).set(database=QA_DATABASE).render_as_string(hide_password=False)
os.environ["VERTICAL_CALCULATION_PREVIEW_ENABLED"] = "true"
os.environ["APP_DEBUG"] = "false"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import Depends
from sqlalchemy import select
from app.api.deps import get_current_user
from app.config import settings
from app.database import get_db
from app.main import app
from app.models.user import User

if make_url(settings.DATABASE_URL).database != QA_DATABASE:
    raise RuntimeError("Refusing to run outside the isolated vertical QA database")


async def qa_admin(db=Depends(get_db)):
    user_id = await db.scalar(select(User.id).limit(1))
    if user_id is None:
        raise RuntimeError("QA database must contain a user")
    return SimpleNamespace(id=user_id, role="ADMIN", moduleAccessRules=[
        {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
        for code in ("MODULE_01_MATERIAL_HUB", "MODULE_02_KNOWLEDGE_BASE",
                     "MODULE_05_ESTIMATE_ENGINE", "MODULE_07_DIGITAL_HOUSE")
    ])


if os.environ.get("QA_TEST_AUTH_OVERRIDE") == "1":
    app.dependency_overrides[get_current_user] = qa_admin

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="warning")
