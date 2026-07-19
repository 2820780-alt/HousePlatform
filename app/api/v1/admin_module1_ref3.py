from __future__ import annotations

from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import CurrentUser
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.services.module1_ref3_read_policy import Module1Ref3ReadActivation
from app.services.module1_ref3_read_projection import (
    CONVERSION_PURPOSE,
    PACKAGING_PURPOSE,
    RULE_PURPOSE,
    UNIT_PURPOSE,
    Ref3ProjectionError,
)


router = APIRouter(
    prefix="/admin/material-hub",
    tags=["admin-material-hub-ref3"],
)

_COMMON_QUERY_PARAMETERS = frozenset({"limit", "offset"})


def _require_admin(user: CurrentUser) -> None:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()


def _reject_unknown_query(request: Request, allowed: frozenset[str]) -> None:
    unknown_parameters = sorted(set(request.query_params) - allowed)
    if unknown_parameters:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=[
                {
                    "input": request.query_params.get(name),
                    "loc": ["query", name],
                    "msg": "Extra inputs are not permitted",
                    "type": "extra_forbidden",
                }
                for name in unknown_parameters
            ],
        )


def _activation(request: Request, purpose: str) -> Module1Ref3ReadActivation:
    activation = getattr(request.app.state, "module1_ref_runtime", None)
    if not isinstance(activation, Module1Ref3ReadActivation) or not activation.is_valid:
        raise NotFoundError("REF-3 administrative projection is not active")
    if (
        activation.ref3_policy is None
        or activation.projection_cache is None
        or not activation.ref3_policy.purpose_allowed(purpose)
    ):
        raise NotFoundError("REF-3 administrative projection is not active")
    return activation


def _common(
    activation: Module1Ref3ReadActivation,
    *,
    total: int,
    limit: int,
    offset: int,
    counts: dict[str, int],
) -> dict[str, Any]:
    return {
        "counts": counts,
        "limit": limit,
        "mode": "ref3_read",
        "offset": offset,
        "read_only": True,
        "ref1_approval_id": activation.ref1_approval_id,
        "ref2_approval_id": activation.ref2_approval_id,
        "ref3_approval_id": activation.ref3_approval_id,
        "runtime_package_id": activation.artifact_set_id,
        "total": total,
    }


@router.get("/ref3-units")
async def get_ref3_units(
    request: Request,
    user: CurrentUser,
    unit_code: str | None = Query(default=None, min_length=1, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin(user)
    _reject_unknown_query(request, _COMMON_QUERY_PARAMETERS | {"unit_code"})
    activation = _activation(request, UNIT_PURPOSE)
    try:
        projection = activation.projection_cache.get_units(UNIT_PURPOSE)
    except Ref3ProjectionError as exc:
        raise NotFoundError("REF-3 unit projection is not available") from exc
    common = _common(
        activation,
        total=len(projection.units),
        limit=limit,
        offset=offset,
        counts=dict(projection.counts),
    )
    common["alias_policy"] = {
        key: list(value) if isinstance(value, tuple) else value
        for key, value in projection.alias_policy.items()
    }
    if unit_code is not None:
        item = projection.get(unit_code)
        if item is None:
            raise NotFoundError("REF-3 unit not found")
        return {**common, "item": item.as_dict()}
    return {
        **common,
        "items": [
            item.as_dict()
            for item in projection.page(offset=offset, limit=limit)
        ],
    }


@router.get("/ref3-conversions")
async def get_ref3_conversions(
    request: Request,
    user: CurrentUser,
    source_unit_code: str | None = Query(default=None, min_length=1, max_length=160),
    target_unit_code: str | None = Query(default=None, min_length=1, max_length=160),
    conversion_kind: Literal["simple", "technical", "formula"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin(user)
    _reject_unknown_query(
        request,
        _COMMON_QUERY_PARAMETERS
        | {"source_unit_code", "target_unit_code", "conversion_kind"},
    )
    activation = _activation(request, CONVERSION_PURPOSE)
    try:
        projection = activation.projection_cache.get_conversions(
            CONVERSION_PURPOSE
        )
    except Ref3ProjectionError as exc:
        raise NotFoundError("REF-3 conversion projection is not available") from exc
    filtered = projection.filtered(
        source_unit_code=source_unit_code,
        target_unit_code=target_unit_code,
        conversion_kind=conversion_kind,
    )
    return {
        **_common(
            activation,
            total=len(filtered),
            limit=limit,
            offset=offset,
            counts=dict(projection.counts),
        ),
        "items": [
            item.as_dict()
            for item in filtered[offset : offset + limit]
        ],
    }


@router.get("/ref3-packaging")
async def get_ref3_packaging(
    request: Request,
    user: CurrentUser,
    material_type_code: str | None = Query(default=None, min_length=1, max_length=160),
    profile_code: str | None = Query(default=None, min_length=1, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin(user)
    _reject_unknown_query(
        request,
        _COMMON_QUERY_PARAMETERS | {"material_type_code", "profile_code"},
    )
    activation = _activation(request, PACKAGING_PURPOSE)
    try:
        projection = activation.projection_cache.get_packaging(
            PACKAGING_PURPOSE
        )
    except Ref3ProjectionError as exc:
        raise NotFoundError("REF-3 packaging projection is not available") from exc
    filtered = projection.filtered(
        material_type_code=material_type_code,
        profile_code=profile_code,
    )
    return {
        **_common(
            activation,
            total=len(filtered),
            limit=limit,
            offset=offset,
            counts=dict(projection.counts),
        ),
        "items": [
            item.as_dict()
            for item in filtered[offset : offset + limit]
        ],
    }


@router.get("/ref3-extended-rules")
async def get_ref3_extended_rules(
    request: Request,
    user: CurrentUser,
    rule_code: str | None = Query(default=None, min_length=1, max_length=160),
    rule_class: Literal["geometry", "coverage", "yield", "consumption"] | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    _require_admin(user)
    _reject_unknown_query(
        request,
        _COMMON_QUERY_PARAMETERS | {"rule_code", "rule_class"},
    )
    activation = _activation(request, RULE_PURPOSE)
    try:
        projection = activation.projection_cache.get_rules(RULE_PURPOSE)
    except Ref3ProjectionError as exc:
        raise NotFoundError("REF-3 rule projection is not available") from exc
    common = _common(
        activation,
        total=len(projection.rules),
        limit=limit,
        offset=offset,
        counts=dict(projection.counts),
    )
    if rule_code is not None:
        item = projection.get(rule_code)
        if item is None:
            raise NotFoundError("REF-3 rule not found")
        return {**common, "item": item.as_dict()}
    filtered = projection.filtered(rule_class=rule_class)
    return {
        **common,
        "total": len(filtered),
        "items": [
            item.as_dict()
            for item in filtered[offset : offset + limit]
        ],
    }
