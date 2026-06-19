import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Enum as SAEnum, ForeignKey, Numeric, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.enums import AdminDecision, MatchCandidateStatus


class MaterialMatchCandidate(Base):
    __tablename__ = "material_match_candidates"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    catalog_product_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("catalog_products.id"), nullable=False, index=True)
    candidate_material_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("materials.id"), index=True)
    match_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    match_reason: Mapped[str | None] = mapped_column(Text)
    ai_suggestion: Mapped[str | None] = mapped_column(Text)
    admin_decision: Mapped[AdminDecision | None] = mapped_column(
        SAEnum(AdminDecision, name="admin_decision", create_constraint=True)
    )
    status: Mapped[MatchCandidateStatus] = mapped_column(
        SAEnum(MatchCandidateStatus, name="match_candidate_status", create_constraint=True),
        default=MatchCandidateStatus.OPEN,
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )

    catalog_product = relationship("CatalogProduct", back_populates="match_candidates")
    candidate_material = relationship("Material")
