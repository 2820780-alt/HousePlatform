from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from app.api.deps import CurrentUser
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.services.module1_ref2_read_policy import Module1Ref2ReadActivation


router = APIRouter(
    prefix="/admin/material-hub/ref2-characteristic-schemas",
    tags=["admin-material-hub-ref2-characteristic-schemas"],
)

_ALLOWED_QUERY_PARAMETERS = frozenset({"material_type_code", "limit", "offset"})
_PURPOSE = "admin_characteristic_schema_read"


@router.get("")
async def get_ref2_characteristic_schemas(
    request: Request,
    user: CurrentUser,
    material_type_code: str | None = Query(default=None, min_length=1, max_length=160),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()

    unknown_parameters = sorted(set(request.query_params) - _ALLOWED_QUERY_PARAMETERS)
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

    activation = getattr(request.app.state, "module1_ref_runtime", None)
    if not isinstance(activation, Module1Ref2ReadActivation) or not activation.is_valid:
        raise NotFoundError("REF-2 characteristic schema projection is not active")
    if activation.projection is None or activation.policy is None:
        raise NotFoundError("REF-2 characteristic schema projection is not active")
    if not activation.policy.purpose_allowed(_PURPOSE):
        raise NotFoundError("REF-2 characteristic schema projection is not active")

    projection = activation.projection
    common = {
        "compatibility_summary": dict(projection.compatibility_summary),
        "counts": dict(projection.counts),
        "mode": "ref2_read",
        "read_only": True,
        "ref1_approval_id": activation.ref1_approval_id,
        "ref2_approval_id": activation.ref2_approval_id,
        "runtime_package_id": activation.artifact_set_id,
        "total": len(projection.schemas),
    }
    if material_type_code is not None:
        schema = projection.get(material_type_code)
        if schema is None:
            raise NotFoundError("REF-2 material type schema not found")
        return {**common, "item": schema.as_detail()}

    return {
        **common,
        "items": [schema.as_summary() for schema in projection.page(offset=offset, limit=limit)],
        "limit": limit,
        "offset": offset,
    }
