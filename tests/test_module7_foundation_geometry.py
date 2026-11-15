import os
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.database import engine as configured_engine
from app.models.module2_technology import Technology
from app.models.module7_geometry import FoundationGeometryRevision
from app.models.user import User
from app.services.module7_foundation_geometry import read_foundation_geometry, save_foundation_geometry
from app.services.module7_foundation_inputs import GeometryDefault
from app.services.module7_strip_geometry import create_object
from app.api.deps import get_current_user
from app.api.v1.module7_foundation_geometry import router
from app.config import settings
from app.database import get_db


@pytest.mark.asyncio
async def test_foundation_geometry_revision_persistence_on_restored_qa(monkeypatch):
    dbname = "houseplatform_vertical_20261113_171244"
    if os.environ.get("ATOM_VERTICAL_QA_DB") != dbname:
        pytest.skip("requires the explicitly restored vertical QA database")
    monkeypatch.setattr(settings, "VERTICAL_CALCULATION_PREVIEW_ENABLED", True)
    engine = create_async_engine(configured_engine.url.set(database=dbname), echo=False)
    try:
        async with engine.connect() as connection:
            columns = await connection.run_sync(lambda sync: inspect(sync).get_columns(
                FoundationGeometryRevision.__tablename__))
            assert {col["name"] for col in columns} == set(FoundationGeometryRevision.__table__.columns.keys())
            assert {col["name"] for col in columns if col["nullable"]} == set()
            await connection.rollback()
            transaction = await connection.begin()
            async with AsyncSession(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
                owner = await db.scalar(select(User.id).limit(1))
                actor = SimpleNamespace(id=owner, role="ADMIN", moduleAccessRules=[
                    {"moduleCode": code, "accessLevel": "ADMIN", "accessScope": "GLOBAL"}
                    for code in ("MODULE_02_KNOWLEDGE_BASE", "MODULE_07_DIGITAL_HOUSE")])
                technology = await db.scalar(select(Technology).where(
                    Technology.technology_code == "FND_SLAB_RIBBED_RC", Technology.status == "DRAFT"))
                obj = await create_object(db, actor=actor, name="QA slab geometry")
                first = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=technology.id,
                    user_values={"geometry.net_area": "50"}, project_values={"geometry.net_area": "60"},
                    trusted_defaults={"geometry.rib_width": GeometryDefault("0.4", "m", "QA source", "VERIFIED"),
                                      "geometry.slab_thickness": GeometryDefault("0.2", "m", "QA source", "VERIFIED")},
                    expected_version=0)
                assert first.inputs["values"]["geometry.net_area"]["source"] == "USER_OVERRIDE"
                assert first.inputs["project_values"]["geometry.net_area"] == "60"
                assert first.inputs["user_values"]["geometry.net_area"] == "50"
                assert first.inputs["values"]["geometry.rib_width"]["default_source"] == "QA source"
                assert "geometry.slab_thickness" in first.inputs["missing"]
                assert "geometry.rib_length" in first.inputs["missing"]
                with pytest.raises(ValueError, match="geometry changed"):
                    await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=technology.id,
                        user_values={}, project_values={}, expected_version=0)
                second = await save_foundation_geometry(db, actor=actor, object_id=obj.id, technology_id=technology.id,
                    user_values={"geometry.net_area": "70", "geometry.slab_thickness": "0.3",
                                 "geometry.rib_length": "20", "geometry.rib_width": "0.4",
                                 "geometry.rib_height": "0.3", "geometry.rib_overlap_volume": "0"},
                    project_values={}, expected_version=1)
                assert second.version == 2 and not second.inputs["missing"]
                assert (await read_foundation_geometry(db, actor=actor, revision_id=first.id)).inputs[
                    "values"]["geometry.net_area"]["value"] == "50"
                other = SimpleNamespace(id=uuid.uuid4(), role="ADMIN", moduleAccessRules=actor.moduleAccessRules)
                with pytest.raises(ValueError, match="not found"):
                    await read_foundation_geometry(db, actor=other, revision_id=first.id)
                app = FastAPI()
                app.include_router(router, prefix="/api/v1")
                app.dependency_overrides[get_current_user] = lambda: actor
                app.dependency_overrides[get_db] = lambda: db
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
                    page = await client.get("/api/v1/admin/module7/foundations/view")
                    assert page.status_code == 200 and "Геометрия фундамента" in page.text
                    fields = await client.get(f"/api/v1/admin/module7/foundations/technologies/{technology.id}/fields")
                    assert fields.status_code == 200 and any(item["key"] == "geometry.rib_length"
                                                               for item in fields.json()["fields"])
                    created = await client.post("/api/v1/admin/module7/foundations/objects", json={"name": "QA API object"})
                    assert created.status_code == 201
                    object_id = created.json()["id"]
                    payload = {"technology_id": str(technology.id), "expected_version": 0,
                               "user_values": {"geometry.net_area": "50"}, "project_values": {}}
                    created = await client.post(f"/api/v1/admin/module7/foundations/objects/{object_id}/revisions",
                                                json=payload)
                    assert created.status_code == 201 and created.json()["version"] == 1
                    fetched = await client.get(f"/api/v1/admin/module7/foundations/revisions/{created.json()['id']}")
                    assert fetched.status_code == 200 and fetched.json()["inputs"]["values"][
                        "geometry.net_area"]["value"] == "50"
                    assert fetched.json()["object_name"] == "QA API object"
                    stale = await client.post(f"/api/v1/admin/module7/foundations/objects/{object_id}/revisions",
                                              json=payload)
                    assert stale.status_code == 422
                    invalid = await client.post(f"/api/v1/admin/module7/foundations/objects/{object_id}/revisions",
                        json={**payload, "expected_version": 1, "user_values": {"geometry.net_area": 3.1}})
                    assert invalid.status_code == 422
                    atomic = await client.post("/api/v1/admin/module7/foundations/objects/with-geometry", json={
                        **payload, "name": "QA atomic object"})
                    assert atomic.status_code == 201 and atomic.json()["version"] == 1
                    objects = await client.get("/api/v1/admin/module7/foundations/objects")
                    assert any(item["revision_id"] == atomic.json()["id"] for item in objects.json())
                    app.dependency_overrides[get_current_user] = lambda: other
                    denied = await client.get(f"/api/v1/admin/module7/foundations/revisions/{created.json()['id']}")
                    assert denied.status_code == 404
                    objects = await client.get("/api/v1/admin/module7/foundations/objects")
                    assert not objects.json()
            await transaction.rollback()
    finally:
        await engine.dispose()
