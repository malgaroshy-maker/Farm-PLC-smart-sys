"""Common response wrappers and pagination schemas."""

from pydantic import BaseModel


class ApiResponse(BaseModel):
    """Standard success wrapper."""

    success: bool = True
    message: str = "OK"
    data: dict | list | None = None


class CommandResponse(BaseModel):
    """Response for command operations."""

    success: bool
    command_id: str | None = None
    status: str
    message: str


class ErrorResponse(BaseModel):
    """Standard error response."""

    success: bool = False
    error_code: str
    message: str


class PaginationMeta(BaseModel):
    """Pagination metadata."""

    total: int
    page: int
    per_page: int
    pages: int
