from __future__ import annotations

from contextlib import asynccontextmanager

import pytest

import app.database as database


class FakeConnection:
    def __init__(self, tables: set[str]) -> None:
        self.tables = tables
        self.calls = []

    async def run_sync(self, fn):
        self.calls.append(fn)
        if fn == database.Base.metadata.create_all:
            return None
        return fn(self)


class FakeEngine:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    async def dispose(self, *, close: bool) -> None:
        assert close is False

    @asynccontextmanager
    async def begin(self):
        yield self.connection


class FakeInspector:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def get_table_names(self) -> list[str]:
        return list(self.connection.tables)


@pytest.mark.asyncio
async def test_startup_never_creates_business_tables(monkeypatch):
    import app.models  # noqa: F401

    connection = FakeConnection(set(database.Base.metadata.tables))
    monkeypatch.setattr(database, "engine", FakeEngine(connection))
    monkeypatch.setattr(database, "inspect", FakeInspector)
    monkeypatch.setattr(database.settings, "APP_ENV", "production")

    await database.init_db()

    assert len(connection.calls) == 1
    assert connection.calls[0] != database.Base.metadata.create_all


@pytest.mark.asyncio
async def test_missing_m2_migration_fails_startup_without_repair(monkeypatch):
    import app.models  # noqa: F401

    tables = set(database.Base.metadata.tables) - {"module2_technologies"}
    connection = FakeConnection(tables)
    monkeypatch.setattr(database, "engine", FakeEngine(connection))
    monkeypatch.setattr(database, "inspect", FakeInspector)
    monkeypatch.setattr(database.settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError, match="module2_technologies"):
        await database.init_db()

    assert len(connection.calls) == 1


@pytest.mark.asyncio
async def test_explicit_isolated_development_schema_creation(monkeypatch):
    import app.models  # noqa: F401

    connection = FakeConnection(set(database.Base.metadata.tables))
    monkeypatch.setattr(database, "engine", FakeEngine(connection))
    monkeypatch.setattr(database, "inspect", FakeInspector)
    monkeypatch.setattr(database.settings, "APP_ENV", "test")

    await database.init_db(create_schema=True)

    assert connection.calls[0] == database.Base.metadata.create_all


@pytest.mark.asyncio
async def test_explicit_production_schema_creation_is_rejected(monkeypatch):
    monkeypatch.setattr(database.settings, "APP_ENV", "production")

    with pytest.raises(RuntimeError, match="restricted"):
        await database.init_db(create_schema=True)
