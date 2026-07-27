"""Error envelope: maps DRF exceptions to a typed, consistent error shape.

Mirrors the sibling giri-cart project's apps/core/exceptions.py pattern
(typed API_ERROR_MAP + normalised {code, detail, fields?} body), scoped down
to the exception types this project actually raises -- no domain-specific
payment/cart exceptions here, just a generic ServiceUnavailableError for the
two AI-generation endpoints' "provider failed" case (scouting reports, club
insights), which previously returned a bare {"error": "..."} string.
"""

from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import APIException, AuthenticationFailed, NotFound
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.views import exception_handler

__all__ = ("API_ERROR_MAP", "custom_exception_handler", "ServiceUnavailableError")

API_ERROR_MAP: dict[str, str] = {
    "AuthenticationFailed": "AUTHENTICATION_FAILED",
    "NotAuthenticated": "NOT_AUTHENTICATED",
    "PermissionDenied": "PERMISSION_DENIED",
    "NotFound": "NOT_FOUND",
    "ValidationError": "VALIDATION_ERROR",
    "Throttled": "RATE_LIMITED",
    "ParseError": "VALIDATION_ERROR",
    "MethodNotAllowed": "METHOD_NOT_ALLOWED",
    "UnsupportedMediaType": "UNSUPPORTED_MEDIA_TYPE",
    "ServiceUnavailableError": "SERVICE_UNAVAILABLE",
}


class ServiceUnavailableError(APIException):
    """Raised when an AI generation call fails (report/insights) -- maps to a
    clean 503, never a fabricated response. Replaces the old manual
    `Response({"error": "..."}, status=503)` pattern in players/clubs views
    so these failures flow through the same typed envelope as every other
    error."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    default_detail = "Service temporarily unavailable. Please try again."
    default_code = "service_unavailable"


def _normalise_error(code: str, data: Any) -> dict[str, Any]:
    """Always produce {code, detail: str, fields?} regardless of DRF error shape."""
    # Dict with a "detail" key -- DRF non-field errors and SimpleJWT
    # (DetailDictMixin) both put the human-readable message here.
    if isinstance(data, dict) and "detail" in data:
        return {"code": code, "detail": str(data["detail"])}

    if isinstance(data, str):
        return {"code": code, "detail": data}

    # List -- non-field ValidationError raised as a list of messages.
    if isinstance(data, list):
        msg = str(data[0]) if data else "Validation failed."
        return {"code": code, "detail": msg}

    # Dict -- field-level ValidationError from a serializer.
    if isinstance(data, dict):
        fields: list[dict[str, str]] = []
        non_field: list[str] = []
        for field, errors in data.items():
            msgs = [str(e) for e in errors] if isinstance(errors, list) else [str(errors)]
            if field == "non_field_errors":
                non_field.extend(msgs)
            else:
                for msg in msgs:
                    fields.append({"field": field, "message": msg})
        detail = non_field[0] if non_field else "Validation failed."
        result: dict[str, Any] = {"code": code, "detail": detail}
        if fields:
            result["fields"] = fields
        return result

    return {"code": code, "detail": str(data)}


def _get_error_code(exc: Exception) -> str:
    """Walk the MRO so subclasses (e.g. simplejwt's InvalidToken) inherit their parent's code."""
    for cls in type(exc).__mro__:
        if cls.__name__ in API_ERROR_MAP:
            return API_ERROR_MAP[cls.__name__]
    return "INTERNAL_ERROR"


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Any:
    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "message_dict") else exc.messages
        exc = DRFValidationError(detail=detail)
    # DRF's own `exception_handler` (called below) converts Http404 ->
    # NotFound and Django's PermissionDenied -> DRF's PermissionDenied
    # internally, but only in its own local scope -- it never hands that
    # converted exception back to the caller. Without doing the same
    # conversion here, `_get_error_code(exc)` below would see the raw
    # Http404/PermissionDenied (neither is in API_ERROR_MAP) and every
    # get_object_or_404() 404 would wrongly report "INTERNAL_ERROR" instead
    # of "NOT_FOUND" -- caught via live verification against the real dev DB.
    elif isinstance(exc, Http404):
        exc = NotFound(*exc.args)
    elif isinstance(exc, DjangoPermissionDenied):
        exc = DRFPermissionDenied(*exc.args)

    response = exception_handler(exc, context)
    if response is None:
        return None
    # DRF downgrades AuthenticationFailed to 403 when the view has no
    # authentication_classes (no WWW-Authenticate header). Always use 401.
    if isinstance(exc, AuthenticationFailed):
        response.status_code = status.HTTP_401_UNAUTHORIZED
    code = _get_error_code(exc)
    response.data = {"error": _normalise_error(code, response.data)}
    return response
