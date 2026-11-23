"""Standard DRF exception handler producing the single error envelope (ARCHITECTURE §14).

Every API error returns::

    {"error": {"code": "...", "message": "...", "fields": {...}}}

DRF's default handler already shapes validation/auth errors consistently; this wrapper
normalises them into the project envelope and keeps the HTTP status intact.
"""

from __future__ import annotations

from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler as drf_exception_handler


def _code_for(exc) -> str:
    if isinstance(exc, APIException):
        return getattr(exc, "default_code", "error") or "error"
    return "server_error"


def api_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    detail = response.data
    message = ""
    fields = None

    if isinstance(detail, dict):
        # DRF validation errors are {"field": [...], "non_field_errors": [...]}
        non_field = detail.pop("non_field_errors", None) if isinstance(detail, dict) else None
        message = " ".join(non_field) if non_field else str(detail)
        if detail:
            fields = detail
    elif isinstance(detail, list):
        message = "; ".join(str(item) for item in detail)
    else:
        message = str(detail)

    code = _code_for(exc)
    return Response(
        {"error": {"code": code, "message": message, "fields": fields}},
        status=response.status_code,
        headers=response.headers,
    )
