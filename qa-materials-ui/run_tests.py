"""Run pytest against the explicitly isolated M1 UI database only."""

import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings
from sqlalchemy.engine import make_url

QA_DATABASE = os.environ.get("M1_UI_TEST_DATABASE", "houseplatform_fnd_m1_m2_20261110")
if QA_DATABASE not in {"houseplatform_ui_clean_20261112", "houseplatform_fnd_m1_m2_20261110", "houseplatform_m1ui_reg_20261111",
                       "houseplatform_m1archive_check_20261111"}:
    raise RuntimeError("Unapproved test database")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
original_init = BaseSettings.__init__


def no_env_file(self, *args, **kwargs):
    kwargs["_env_file"] = None
    original_init(self, *args, **kwargs)


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
    raise RuntimeError("Refusing to run tests outside the isolated QA database")

import pytest

raise SystemExit(pytest.main(sys.argv[1:]))
