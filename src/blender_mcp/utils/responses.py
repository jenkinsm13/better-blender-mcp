"""Structured response builders for MCP tool responses."""

from __future__ import annotations
from typing import Any


def success(**kwargs: Any) -> dict[str, Any]:
    """Build a success response with arbitrary key-value data."""
    return {"status": "ok", **kwargs}


def error(error_type: str, message: str, **context: Any) -> dict[str, Any]:
    """Build a structured error response."""
    result: dict[str, Any] = {
        "status": "error",
        "error": error_type,
        "message": message,
    }
    if context:
        result["context"] = context
    return result
