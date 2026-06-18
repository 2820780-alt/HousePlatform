import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, Integer, Numeric, ForeignKey, Index
from sqlalchemy.orm import Mapped, mapped_column
from app.database import Base
from decimal import Decimal


class RuleMemory(Base):
    """
    Rule Memory Layer — накопление паттернов из подтверждённых решений.
    НЕ является ML-моделью. Это эвристические правила, накопленные из
    действий поставщиков и администраторов.
    """
    __tablename__ = "rule_memory"
    __table_args__ = (
        Index("ix_rule_memory_pattern", "normalized_pattern"),
        Index("ix_rule_memory_material", "material_id"),
        Index("ix_rule_memory_category", "category_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)

    # Паттерн для сопоставления
    normalized_pattern: Mapped[str] = mapped_column(Text, nullable=False)

    # Куда привязывать при совпадении
    material_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("materials.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("material_categories.id"),
    )

    # Ключевые атрибуты для дополнительной проверки (JSON строка)
    attributes_json: Mapped[str | None] = mapped_column(Text)

    # Дополнительный boost к confidence при совпадении с паттерном
    # 0.00–0.25
    confidence_boost: Mapped[Decimal] = mapped_column(
        Numeric(5, 4), nullable=False, default=Decimal("0.10")
    )

    # Сколько раз паттерн был подтверждён (растёт → больше доверия)
    confirmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Кто подтвердил паттерн первым
    # "supplier_confirm" | "admin_approve"
    source: Mapped[str] = mapped_column(String(50), nullable=False)

    # Поставщик, который впервые создал паттерн (опционально)
    source_supplier_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("suppliers.id"),
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def get_confidence_boost(self) -> Decimal:
        """Буст зависит от количества подтверждений."""
        if self.confirmed_count >= 10:
            return Decimal("0.20")
        elif self.confirmed_count >= 4:
            return Decimal("0.15")
        else:
            return Decimal("0.10")
