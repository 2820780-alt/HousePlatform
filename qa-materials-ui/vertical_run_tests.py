"""Run tests only against the explicitly restored vertical QA database."""
import sys

import vertical_qa_server  # asserts the isolated DB before loading application modules
from app.config import settings

settings.VERTICAL_CALCULATION_PREVIEW_ENABLED = False
import pytest

raise SystemExit(pytest.main(sys.argv[1:]))
