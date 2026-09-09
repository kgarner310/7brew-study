"""Shared response envelopes."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class Page[T](BaseModel):
    """A page of results with the cursor inputs echoed back."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int = Field(description="Total rows matching the filter, ignoring paging.")
    limit: int
    offset: int

    @property
    def has_more(self) -> bool:
        return self.offset + len(self.items) < self.total


class ErrorResponse(BaseModel):
    """A machine-readable error."""

    error: str
    detail: str | None = None
    code: str | None = None
