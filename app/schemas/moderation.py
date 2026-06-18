from uuid import UUID

from pydantic import BaseModel


class ModerationApprove(BaseModel):
    material_id: UUID | None = None


class ModerationReject(BaseModel):
    reason: str | None = None


class ModerationCreateMaterial(BaseModel):
    canonical_name: str | None = None
    category_id: UUID | None = None
    brand: str | None = None
    manufacturer: str | None = None
