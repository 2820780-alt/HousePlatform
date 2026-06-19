import uuid
from datetime import datetime
from sqlalchemy import String, Boolean, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base
from app.models.enums import UnitType


class Unit(Base):
    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    unit_type: Mapped[UnitType] = mapped_column(SAEnum(UnitType, name="unit_type", create_constraint=True), nullable=False, index=True)
    is_base: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())

    aliases = relationship("UnitAlias", back_populates="unit")
