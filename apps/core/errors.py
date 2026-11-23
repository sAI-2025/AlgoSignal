"""Standard JSON error envelope for chart/API views (ARCHITECTURE §14).

Views are thin helpers — this is the one place the error body shape is defined, so every
endpoint returns:

    {"error": {"code": "VALIDATION_ERROR", "message": "...", "fields": {...}}}
"""

from __future__ import annotations

from typing import Any

from django.http import JsonResponse


def error_response(
    code: str,
    message: str,
    *,
    status: int = 400,
    fields: dict[str, Any] | None = None,
) -> JsonResponse:
    """Return a ``JsonResponse`` with the single error envelope."""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if fields:
        body["error"]["fields"] = fields
    return JsonResponse(body, status=status)
