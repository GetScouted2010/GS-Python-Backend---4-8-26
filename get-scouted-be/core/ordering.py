"""Ordering that sorts missing values LAST, in either direction.

DRF's stock `OrderingFilter` hands the field names straight to the database,
and PostgreSQL sorts NULLs FIRST on a descending sort. For a "best first"
score list that is exactly wrong: the players with NO score would head the
list. It went unnoticed while almost every player had an impact score; with
2025-2026 as the default season ~70% of its players have no compatibility or
transfer-probability score (their club has no playstyle data), so sorting by
those would open with thousands of blanks.
"""

from __future__ import annotations

from django.db.models import F
from rest_framework.filters import OrderingFilter


class NullsLastOrderingFilter(OrderingFilter):
    def filter_queryset(self, request, queryset, view):
        ordering = self.get_ordering(request, queryset, view)
        if not ordering:
            return queryset
        expressions = []
        for term in ordering:
            field = term.lstrip("-")
            expressions.append(
                F(field).desc(nulls_last=True) if term.startswith("-") else F(field).asc(nulls_last=True)
            )
        return queryset.order_by(*expressions)
