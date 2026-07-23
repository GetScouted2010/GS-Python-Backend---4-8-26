"""Shared error/envelope helpers for Phase 4's score services."""


def null_with_reason(field: str, code: str) -> dict:
    """Shared missing-data envelope used identically by all 4 scores.

    Every score endpoint that cannot compute a value (no club context,
    unresolved playing style, missing TFM features, etc.) returns this exact
    `{"<field>": null, "reason": "<code>"}` shape instead of a fabricated
    number -- CONTEXT.md's locked envelope shape.
    """
    return {field: None, "reason": code}
