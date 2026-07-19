from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.api.deps import CurrentUser
from app.core.exceptions import ForbiddenError, NotFoundError
from app.models.enums import UserRole
from app.services.module1_ref1_read_policy import (
    APPROVAL_VERSION,
    Module1Ref1ReadActivation,
)
from app.services.module1_ref2_read_policy import Module1Ref2ReadActivation


router = APIRouter(
    prefix="/admin/material-hub/ref1-taxonomy",
    tags=["admin-material-hub-ref1-taxonomy"],
)


@router.get("")
async def get_ref1_taxonomy(
    request: Request,
    user: CurrentUser,
    code: str | None = Query(default=None, max_length=160),
    name: str | None = Query(default=None, max_length=240),
    parent: str | None = Query(default=None, max_length=160),
) -> dict[str, Any]:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError()

    runtime_activation = getattr(request.app.state, "module1_ref_runtime", None)
    if isinstance(runtime_activation, Module1Ref2ReadActivation):
        activation = runtime_activation.ref1_activation
    elif isinstance(runtime_activation, Module1Ref1ReadActivation):
        activation = runtime_activation
    else:
        activation = None
    if activation is None or not activation.is_valid:
        raise NotFoundError("REF-1 taxonomy projection is not active")
    if activation.projection is None or activation.policy is None:
        raise NotFoundError("REF-1 taxonomy projection is not active")
    if not activation.policy.purpose_allowed("admin_taxonomy_read"):
        raise NotFoundError("REF-1 taxonomy projection is not active")

    projection = activation.projection.filtered(code=code, name=name, parent=parent)
    return {
        "approval_id": activation.approval_id,
        "approval_version": APPROVAL_VERSION,
        "artifact_set_id": activation.artifact_set_id,
        "counts": {
            "groups": len(projection.groups),
            "material_types": len(projection.material_types),
        },
        "filters_persisted": False,
        "groups": [item.as_dict() for item in projection.groups],
        "material_types": [item.as_dict() for item in projection.material_types],
        "mode": runtime_activation.mode,
        "read_only": True,
        "ref_only_write_eligibility": False,
    }
