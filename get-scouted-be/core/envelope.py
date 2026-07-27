"""Response envelope renderer. Wraps every JSON response in { data, meta }.

Mirrors the pattern used by the sibling giri-cart project (apps/core/envelope.py)
so both backends share one consistent API response shape. No request-id
middleware exists in this project (unlike giri-cart's), so `meta.request_id`
is always a fresh uuid4 per request rather than reused across a request's
lifecycle -- fine for its purpose (a correlation id a client can quote in a
bug report), just not wired to logging yet.
"""

from __future__ import annotations

import uuid
from typing import Any

from rest_framework.renderers import JSONRenderer

__all__ = ("EnvelopeRenderer",)


class EnvelopeRenderer(JSONRenderer):
    media_type = "application/json"
    format = "json"

    def render(
        self,
        data: Any,
        accepted_media_type: str | None = None,
        renderer_context: dict | None = None,
    ) -> bytes:
        renderer_context = renderer_context or {}
        request = renderer_context.get("request")

        # Pass through if already an envelope (defensive -- avoids double-wrapping
        # if a view or test ever constructs the envelope shape itself).
        if isinstance(data, dict) and "data" in data and "meta" in data and len(data) == 2:
            return super().render(data, accepted_media_type, renderer_context)

        request_id = getattr(request, "_request_id", None) or str(uuid.uuid4())
        meta: dict[str, Any] = {"request_id": request_id}

        # Paginated list response: { items: [...], pagination: {...} }
        # Promote pagination to root: { data: [...], meta: ..., pagination: {...} }
        if isinstance(data, dict) and set(data.keys()) == {"items", "pagination"}:
            envelope = {"data": data["items"], "meta": meta, "pagination": data["pagination"]}
            return super().render(envelope, accepted_media_type, renderer_context)

        # Error responses (from core.exceptions.custom_exception_handler): place
        # error at the top level, NOT under data -- {error: {...}, meta} instead
        # of {data: {error: ...}, meta}.
        if isinstance(data, dict) and "error" in data and len(data) == 1:
            envelope = {"error": data["error"], "meta": meta}
        else:
            envelope = {"data": data, "meta": meta}
        return super().render(envelope, accepted_media_type, renderer_context)
