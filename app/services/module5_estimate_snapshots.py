"""Create reproducible, owner-scoped preliminary M5 calculations."""
from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import asdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permission_guard import require_permission
from app.core.exceptions import ForbiddenError
from app.models.provider_work_cost_offer import ProviderWorkCostOffer
from app.models.module2_calculation_block import TechnologyCalculationBlock
from app.models.module5_estimate_snapshot import EstimatePreviewSnapshot
from app.services.audit_service import log_event
from app.services.module1_offer_qualification import quote_current_offers
from app.services.module1_provider_work_cost_offers import _apply_list_permissions
from app.services.module2_calculation_blocks import _validate_technology_roles, decode_definition
from app.services.module5_calculation_preview import PROTECTED_GEOMETRY_INPUTS, StatementBinding, calculate_statement_preview
from app.services.module7_strip_geometry import read_strip_geometry

MODULE5_CODE = "MODULE_05_ESTIMATE_ENGINE"
MODULE1_CODE = "MODULE_01_MATERIAL_HUB"


def _json(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str, sort_keys=True))


async def create_estimate_preview(
    db: AsyncSession, *, actor: object, geometry_revision_id: uuid.UUID, region: str, terms: str,
    accounting_keys: Mapping[tuple[str, str], str],
    parameter_values: Mapping[tuple[str, str], str] | None = None,
) -> EstimatePreviewSnapshot:
    require_permission(actor, MODULE5_CODE, "CREATE")
    require_permission(actor, MODULE1_CODE, "VIEW")
    if not region.strip() or not terms.strip():
        raise ValueError("region and price conditions are required")
    geometry = await read_strip_geometry(db, actor=actor, revision_id=geometry_revision_id)
    rows = (await db.scalars(select(TechnologyCalculationBlock).where(
        TechnologyCalculationBlock.technology_id == geometry.technology_id).order_by(
        TechnologyCalculationBlock.position))).all()
    quote_date = date.today()
    blocks, bindings, quotes, quote_errors, block_issues = [], [], {}, {}, {}
    for row in rows:
        block = decode_definition(row.definition, block_id=str(row.id), name=row.name,
                                  material_id=str(row.material_id) if row.material_id else None, work_code=row.work_code)
        blocks.append(block)
        try:
            await _validate_technology_roles(db, geometry.technology_id, block)
        except ValueError:
            block_issues[block.id] = ("TECHNOLOGY_ROLE_INVALID",)
        for kind, resource, output in (("MATERIAL", block.material_id, block.material_output_id),
                                       ("WORK", block.work_code, block.work_output_id)):
            if output is None:
                continue
            scope = (accounting_keys.get((block.id, kind)) or "").strip()
            if not scope or len(scope) > 255:
                raise ValueError("each material and work output requires an explicit accounting key")
            role_id = block.material_requirement_id if kind == "MATERIAL" else block.work_step_id
            bindings.append(StatementBinding(f"{block.id}:{kind}", block.id, kind, resource, output, scope, role_id))
            if resource and (kind, resource) not in quotes:
                try:
                    quotes[(kind, resource)] = await quote_current_offers(
                        db, material_id=uuid.UUID(resource) if kind == "MATERIAL" else None,
                        work_code=resource if kind == "WORK" else None,
                        region=region, terms=terms, as_of=quote_date, actor=actor)
                except ValueError:
                    quote_errors[f"{kind}:{resource}"] = "PRICE_CONTEXT_OR_RESOURCE_INVALID"
    values = {"geometry.length": (geometry.length_m, "m"), "geometry.width": (geometry.width_m, "m"),
              "geometry.height": (geometry.height_m, "m")}
    allowed_parameters = {(block.id, item.input_key): item for block in blocks for item in block.parameters}
    submitted = parameter_values or {}
    if set(submitted) - set(allowed_parameters) or any(key in PROTECTED_GEOMETRY_INPUTS for _, key in submitted):
        raise ValueError("unknown calculation parameter")
    explicit_parameters = {}
    for key, raw in submitted.items():
        if not isinstance(raw, str) or len(raw) > 80:
            raise ValueError("invalid calculation parameter")
        try:
            value = Decimal(raw.strip().replace(",", "."))
        except InvalidOperation:
            raise ValueError("invalid calculation parameter") from None
        if not value.is_finite() or value.adjusted() > 24 or value.adjusted() < -24:
            raise ValueError("invalid calculation parameter")
        explicit_parameters[key] = (value, allowed_parameters[key].unit)
    preview = calculate_statement_preview(tuple(blocks), tuple(bindings), values, quotes,
                                          allow_preliminary_defaults=True, parameter_values=explicit_parameters,
                                          block_issues=block_issues)
    graph = _json([asdict(block) for block in blocks])
    graph_hash = hashlib.sha256(json.dumps(graph, ensure_ascii=True, sort_keys=True,
                                           separators=(",", ":")).encode()).hexdigest()
    payload = _json({"schema_version": 1, "mode": "PREVIEW", "geometry": {
        "revision_id": geometry.id, "version": geometry.version, "technology_id": geometry.technology_id,
        "length_m": geometry.length_m, "width_m": geometry.width_m, "height_m": geometry.height_m},
        "region": region, "terms": terms, "graph": graph, "graph_hash": graph_hash,
        "parameters": [{"block_id": key[0], "input_key": key[1], "value": value[0], "unit": value[1]}
                       for key, value in explicit_parameters.items()],
        "quotes": [{"kind": key[0], "resource_id": key[1], "quote": asdict(quote)}
                   for key, quote in quotes.items()], "quote_errors": quote_errors, "result": asdict(preview)})
    snapshot = EstimatePreviewSnapshot(id=uuid.uuid4(), owner_user_id=getattr(actor, "id"),
                                       geometry_revision_id=geometry.id, mode="PREVIEW", payload=payload)
    db.add(snapshot)
    await db.flush()
    await log_event(db, "M5_PREVIEW_CREATED", "EstimatePreviewSnapshot", snapshot.id, getattr(actor, "id"),
                    {"geometry_revision_id": str(geometry.id), "complete": preview.complete})
    return snapshot


async def read_estimate_preview(db: AsyncSession, *, actor: object, snapshot_id: uuid.UUID) -> EstimatePreviewSnapshot:
    require_permission(actor, MODULE5_CODE, "VIEW")
    require_permission(actor, MODULE1_CODE, "VIEW")
    snapshot = await db.scalar(select(EstimatePreviewSnapshot).where(
        EstimatePreviewSnapshot.id == snapshot_id, EstimatePreviewSnapshot.owner_user_id == getattr(actor, "id", None)))
    if snapshot is None:
        raise ValueError("estimate preview not found")
    await read_strip_geometry(db, actor=actor, revision_id=snapshot.geometry_revision_id)
    work_offer_ids = set()
    for entry in snapshot.payload.get("quotes", []):
        if entry.get("kind") == "WORK":
            quote = entry.get("quote", {})
            work_offer_ids.update(item["offer_id"] for item in quote.get("contributors", []))
            work_offer_ids.update(item[0] for item in quote.get("excluded", []))
    if work_offer_ids:
        query = _apply_list_permissions(select(ProviderWorkCostOffer.id).where(
            ProviderWorkCostOffer.id.in_([uuid.UUID(item) for item in work_offer_ids])), actor, owner_user_id=None)
        visible = {str(item) for item in (await db.scalars(query)).all()}
        if visible != work_offer_ids:
            raise ForbiddenError("Work offer access is required to view this calculation")
    return snapshot
