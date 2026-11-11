from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.models.enums import MaterialStatus
from app.services.rule_memory import find_rule_for_product


@pytest.mark.asyncio
async def test_archived_rule_is_not_selected_and_active_rule_remains_available():
    archived = SimpleNamespace(material=SimpleNamespace(status=MaterialStatus.ARCHIVED),
                               category_id=None, normalized_pattern="concrete mix")
    active = SimpleNamespace(material=SimpleNamespace(status=MaterialStatus.VERIFIED),
                             category_id=None, normalized_pattern="concrete mix")
    result = SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [archived, active]))
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    product = SimpleNamespace(raw_name="concrete mix", normalized_name=None, raw_category=None)

    assert await find_rule_for_product(db, product) is active
