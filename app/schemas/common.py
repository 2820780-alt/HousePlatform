from pydantic import BaseModel
from typing import TypeVar, Generic, Sequence

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: Sequence[T]
    total: int
    offset: int
    limit: int
