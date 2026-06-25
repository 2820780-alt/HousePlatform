from enum import StrEnum
from typing import Final


class AccessScope(StrEnum):
    NONE = "NONE"
    GLOBAL = "GLOBAL"
    OWN = "OWN"
    RELEVANT = "RELEVANT"
    LIMITED = "LIMITED"


ACCESS_SCOPES: Final[tuple[str, ...]] = tuple(scope.value for scope in AccessScope)


def is_valid_access_scope(value: str) -> bool:
    return value in ACCESS_SCOPES
