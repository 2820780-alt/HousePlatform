import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


USER_MODULE_QUICK_ACTION_STATUSES: tuple[str, ...] = (
    "ACTIVE",
    "DISABLED",
    "BROKEN_CONFIG",
    "MODULE_DISABLED",
    "NO_LONGER_AVAILABLE",
    "LOADING",
    "ERROR",
)

ATOM_CARD_ACCENTS: tuple[str, ...] = (
    "blue",
    "cyan",
    "green",
    "orange",
    "red",
    "purple",
)


class UserModuleQuickAction(Base):
    __tablename__ = "user_module_quick_actions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    workspace_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("workspaces.id"), index=True)
    active_region_code: Mapped[str | None] = mapped_column(String(80), index=True)

    source_module_code: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    feature_code: Mapped[str | None] = mapped_column(String(120), index=True)
    action_key: Mapped[str] = mapped_column(String(160), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    icon: Mapped[str | None] = mapped_column(String(80))

    route: Mapped[str | None] = mapped_column(String(500))
    deep_link: Mapped[str | None] = mapped_column(String(500))

    saved_config_ref: Mapped[str | None] = mapped_column(String(255), index=True)
    config_snapshot: Mapped[dict | None] = mapped_column(JSON)

    order: Mapped[int] = mapped_column("sort_order", Integer, default=1000, nullable=False, index=True)
    is_visible_in_module_bar: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    is_pinned_to_atom_card: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    atom_card_order: Mapped[int | None] = mapped_column(Integer, index=True)
    atom_card_accent: Mapped[str | None] = mapped_column(String(20), index=True)

    status: Mapped[str] = mapped_column(String(40), default="ACTIVE", nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(nullable=False, default=lambda: datetime.utcnow())
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        default=lambda: datetime.utcnow(),
        onupdate=lambda: datetime.utcnow(),
    )


@dataclass(frozen=True)
class QuickActionCandidate:
    sourceModuleCode: str
    actionKey: str
    title: str
    featureCode: str | None = None
    description: str | None = None
    icon: str | None = None
    route: str | None = None
    deepLink: str | None = None
    canSaveAsQuickAction: bool = True
    canPinToAtomCard: bool = False
    configMode: str = "NO_CONFIG"
    currentConfigRef: str | None = None
    currentConfigSnapshot: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class AddUserQuickActionRequest:
    userId: str
    sourceModuleCode: str
    actionKey: str
    title: str
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    featureCode: str | None = None
    description: str | None = None
    icon: str | None = None
    route: str | None = None
    deepLink: str | None = None
    savedConfigRef: str | None = None
    configSnapshot: dict[str, Any] | None = None
    pinToAtomCard: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class UpdateUserQuickActionRequest:
    title: str | None = None
    order: int | None = None
    isVisibleInModuleBar: bool | None = None
    isPinnedToAtomCard: bool | None = None
    atomCardOrder: int | None = None
    atomCardAccent: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuickActionRunContext:
    userId: str
    sourceModuleCode: str
    actionKey: str
    quickActionId: str | None = None
    workspaceId: str | None = None
    activeRegionCode: str | None = None
    activeCabinetId: str | None = None
    route: str | None = None
    deepLink: str | None = None
    savedConfigRef: str | None = None
    configSnapshot: dict[str, Any] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class QuickActionRunResult:
    status: str
    sourceModuleCode: str
    actionKey: str
    quickActionId: str | None = None
    route: str | None = None
    deepLink: str | None = None
    message: str | None = None
    state: str | None = None
    requiresModuleHandler: bool = True
    resultRef: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
