from enum import StrEnum
from typing import Final


class AccessLevel(StrEnum):
    NO_ACCESS = "NO_ACCESS"
    VIEW = "VIEW"
    CREATE = "CREATE"
    EDIT = "EDIT"
    APPROVE = "APPROVE"
    ADMIN = "ADMIN"


ACCESS_LEVELS: Final[tuple[str, ...]] = tuple(level.value for level in AccessLevel)

ACCESS_SCOPES_ARE_NOT_ACCESS_LEVELS: Final[tuple[str, ...]] = (
    "VIEW_OWN",
    "ADMIN_OWN",
    "LIMITED_VIEW",
    "VIEW_RELEVANT",
)


def is_valid_access_level(value: str) -> bool:
    return value in ACCESS_LEVELS


def is_access_scope(value: str) -> bool:
    return value in ACCESS_SCOPES_ARE_NOT_ACCESS_LEVELS
