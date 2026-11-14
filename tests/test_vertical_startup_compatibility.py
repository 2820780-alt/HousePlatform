import app.models  # noqa: F401
from app.database import Base, VERTICAL_PREVIEW_TABLES, _required_schema_tables


def test_disabled_preview_does_not_require_unmigrated_optional_tables():
    assert VERTICAL_PREVIEW_TABLES <= set(Base.metadata.tables)
    required = _required_schema_tables(vertical_preview_enabled=False)
    assert not (required & VERTICAL_PREVIEW_TABLES)
    assert required == set(Base.metadata.tables) - VERTICAL_PREVIEW_TABLES


def test_enabled_preview_requires_every_vertical_table():
    assert _required_schema_tables(vertical_preview_enabled=True) == set(Base.metadata.tables)
