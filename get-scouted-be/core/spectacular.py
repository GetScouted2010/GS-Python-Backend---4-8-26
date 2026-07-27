"""drf-spectacular postprocessing hooks -- documents the response envelope
shape (core.envelope.EnvelopeRenderer / core.exceptions.custom_exception_handler)
as reusable OpenAPI schema components, mirroring the sibling giri-cart
project's apps/core/spectacular.py."""

from __future__ import annotations

from typing import Any


def add_error_schemas(result: dict[str, Any], generator: Any, request: Any, public: bool) -> dict[str, Any]:
    """Inject FieldError, ApiError, and ErrorEnvelope into components/schemas."""
    schemas: dict[str, Any] = result.setdefault("components", {}).setdefault("schemas", {})

    schemas["FieldError"] = {
        "type": "object",
        "description": "A single field-level validation error.",
        "properties": {
            "field": {"type": "string", "description": "Name of the invalid field"},
            "message": {"type": "string", "description": "Human-readable error for this field"},
        },
        "required": ["field", "message"],
    }

    schemas["ApiError"] = {
        "type": "object",
        "description": "Typed error body present in every non-2xx response.",
        "properties": {
            "code": {
                "type": "string",
                "enum": [
                    "VALIDATION_ERROR",
                    "NOT_AUTHENTICATED",
                    "AUTHENTICATION_FAILED",
                    "PERMISSION_DENIED",
                    "NOT_FOUND",
                    "RATE_LIMITED",
                    "METHOD_NOT_ALLOWED",
                    "UNSUPPORTED_MEDIA_TYPE",
                    "SERVICE_UNAVAILABLE",
                    "INTERNAL_ERROR",
                ],
                "description": "Machine-readable error code.",
            },
            "detail": {
                "type": "string",
                "description": "Human-readable summary. Always a string -- safe to display directly.",
            },
            "fields": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/FieldError"},
                "description": "Per-field errors. Present only on VALIDATION_ERROR when field attribution is available.",
            },
        },
        "required": ["code", "detail"],
    }

    schemas["ErrorEnvelope"] = {
        "type": "object",
        "description": "Wrapper for all error responses.",
        "properties": {
            "error": {"$ref": "#/components/schemas/ApiError"},
            "meta": {
                "type": "object",
                "properties": {
                    "request_id": {
                        "type": "string",
                        "format": "uuid",
                        "description": "Unique ID for this request -- include in bug reports.",
                    }
                },
                "required": ["request_id"],
            },
        },
        "required": ["error", "meta"],
    }

    return result
