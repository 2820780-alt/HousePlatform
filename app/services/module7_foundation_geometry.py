"""Owner-scoped immutable revisions of typed foundation geometry."""
from __future__ import annotations

import uuid
from typing import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_guard import require_permission
from app.models.module2_technology import TechnologyDefaultAssumption
from app.models.module7_geometry import DigitalHouseObject, FoundationGeometryRevision
from app.services.audit_service import log_event
from app.services.module2_default_assumptions import FOUNDATION_EXPLICIT_INPUTS, may_use_default
from app.services.module7_foundation_inputs import FOUNDATION_FIELDS, GeometryDefault, resolve_foundation_geometry
from app.services.module7_strip_geometry import MODULE7_CODE, _technology

EXPLICIT_INPUT_ALIASES = {
    "geometry.slab_thickness": "SLAB_THICKNESS_MM",
    "geometry.rib_height": "RIB_HEIGHT_MM",
    "pile.length": "PILE_LENGTH_MM",
    "pile.diameter": "PILE_DIAMETER_MM",
    "geometry.width": "GRILLAGE_WIDTH_MM",
    "geometry.height": "GRILLAGE_HEIGHT_MM",
    "element.width": "COLUMN_WIDTH_MM",
    "geometry.wall_height": "WALL_HEIGHT_MM",
}


async def _m2_geometry_defaults(db, technology) -> dict[str, GeometryDefault]:
    fields = {item.key: item for item in FOUNDATION_FIELDS.get(technology.technology_code, ())}
    rows = (await db.scalars(select(TechnologyDefaultAssumption).where(
        TechnologyDefaultAssumption.technology_id == technology.id,
        TechnologyDefaultAssumption.status == "ACTIVE", TechnologyDefaultAssumption.value_type == "NUMBER",
        TechnologyDefaultAssumption.parameter_code.in_(fields)))).all()
    defaults = {}
    for row in rows:
        if technology.technology_code == "FND_SLAB_USHP" and row.parameter_code.startswith("edge."):
            continue
        historical_code = EXPLICIT_INPUT_ALIASES.get(row.parameter_code, row.parameter_code)
        if (not may_use_default(technology, row) or
                (technology.technology_code, historical_code) in FOUNDATION_EXPLICIT_INPUTS or
                row.unit != fields[row.parameter_code].unit):
            continue
        if row.parameter_code in defaults:
            raise ValueError("multiple M2 defaults for a geometry parameter")
        value = (row.default_value or {}).get("value")
        if value is None or isinstance(value, (bool, float)):
            continue
        defaults[row.parameter_code] = GeometryDefault(str(value), row.unit,
            f"M2:{row.assumption_code}:revision:{row.revision}", "PRELIMINARY")
    return defaults


async def save_foundation_geometry(
    db: AsyncSession, *, actor: object, object_id: uuid.UUID, technology_id: uuid.UUID,
    user_values: Mapping[str, object], project_values: Mapping[str, object], expected_version: int,
    trusted_defaults: Mapping[str, GeometryDefault] | None = None, allow_preliminary: bool = False,
) -> FoundationGeometryRevision:
    require_permission(actor, MODULE7_CODE, "EDIT")
    owner_id = getattr(actor, "id", None)
    item = await db.scalar(select(DigitalHouseObject).where(
        DigitalHouseObject.id == object_id, DigitalHouseObject.owner_user_id == owner_id).with_for_update())
    if item is None:
        raise ValueError("object not found")
    technology = await _technology(db, technology_id, actor)
    if trusted_defaults is None:
        trusted_defaults = await _m2_geometry_defaults(db, technology)
    trusted_defaults = {key: value for key, value in trusted_defaults.items()
                        if (technology.technology_code, EXPLICIT_INPUT_ALIASES.get(key, key))
                        not in FOUNDATION_EXPLICIT_INPUTS and not
                        (technology.technology_code == "FND_SLAB_USHP" and key.startswith("edge."))}
    explicit_user = resolve_foundation_geometry(technology.technology_code, user_values=user_values, project_values={})
    explicit_project = resolve_foundation_geometry(technology.technology_code, user_values={}, project_values=project_values)
    result = resolve_foundation_geometry(technology.technology_code, user_values=user_values,
        project_values=project_values, defaults=trusted_defaults, allow_preliminary=allow_preliminary)
    current = (await db.scalar(select(func.max(FoundationGeometryRevision.version)).where(
        FoundationGeometryRevision.object_id == object_id))) or 0
    if current != expected_version:
        raise ValueError("geometry changed; refresh before saving")
    inputs = {"schema_version": 1, "technology_code": technology.technology_code,
              "allow_preliminary": allow_preliminary,
              "user_values": {key: str(value) for key, (value, _) in explicit_user.values.items() if key in user_values},
              "project_values": {key: str(value) for key, (value, _) in explicit_project.values.items() if key in project_values},
              "values": {key: {"value": str(value), "unit": unit, "source": result.provenance[key],
                               "default_source": result.default_sources.get(key)}
                         for key, (value, unit) in result.values.items()},
              "missing": list(result.missing), "warnings": list(result.warnings)}
    revision = FoundationGeometryRevision(id=uuid.uuid4(), object_id=object_id, version=current + 1,
        technology_id=technology_id, inputs=inputs, created_by_user_id=owner_id)
    db.add(revision)
    await db.flush()
    await log_event(db, "M7_FOUNDATION_GEOMETRY_SAVED", "FoundationGeometryRevision", revision.id, owner_id,
                    {"object_id": str(object_id), "version": revision.version, "technology_id": str(technology_id)})
    return revision


async def read_foundation_geometry(db: AsyncSession, *, actor: object,
                                   revision_id: uuid.UUID) -> FoundationGeometryRevision:
    require_permission(actor, MODULE7_CODE, "VIEW")
    result = await db.scalar(select(FoundationGeometryRevision).join(
        DigitalHouseObject, DigitalHouseObject.id == FoundationGeometryRevision.object_id).where(
        FoundationGeometryRevision.id == revision_id, DigitalHouseObject.owner_user_id == getattr(actor, "id", None)))
    if result is None:
        raise ValueError("geometry not found")
    await _technology(db, result.technology_id, actor)
    return result
