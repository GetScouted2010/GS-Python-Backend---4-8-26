"""Project-wide DRF pagination, wired as DEFAULT_PAGINATION_CLASS
(config/settings/base.py).

Emits { items, pagination } from get_paginated_response -- core.envelope.
EnvelopeRenderer recognises this exact shape and promotes it to the response
envelope's top level: { data: <items>, meta, pagination }. This mirrors the
sibling giri-cart project's apps/core/pagination.py (EnvelopedPageNumberPagination),
adapted to this project's existing snake_case field-naming convention (this
project's serializers use market_value/impact_score etc, not camelCase) and
its existing ?page_size= query param (unchanged, so no client-facing break
for callers already using it).

Now wired project-wide as DEFAULT_PAGINATION_CLASS: the old carve-out reason
("would retroactively paginate /api/v1/auth/admin/users/, which returns a
plain list and isn't written to expect a paginated envelope") no longer
applies now that every response is envelope-wrapped either way -- a bare
list becomes {data: [...], meta}, a paginated one becomes {data: [...],
meta, pagination}, so applying real pagination everywhere (rather than an
unbounded plain list) is now a pure improvement, not a breaking shape change
for any endpoint that wasn't already paginated.

StandardResultsPagination: 25 rows/page, client-adjustable via ?page_size=,
hard-capped at 100 so no caller can request an unbounded page across the
41,708-player table.

IdsBypassPagination is used by the players/clubs list views' `pagination_class`:
when the caller passes ?ids=<uuid>,<uuid>,... (CRUD-05 multi-fetch) they have
already named an exact, bounded set, so the response is returned unpaginated
(a bare list) rather than forcing a page-2 round-trip for a 3-5 item
comparison. Returning None from paginate_queryset is DRF's documented "do not
paginate this response" signal that ListModelMixin.list() checks for -- the
envelope renderer still wraps the resulting bare list as {data: [...], meta}.
"""

from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardResultsPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data) -> Response:
        return Response(
            {
                "items": data,
                "pagination": {
                    "page": self.page.number,
                    "page_size": self.page.paginator.per_page,
                    "total_items": self.page.paginator.count,
                    "has_next_page": self.page.has_next(),
                    "next_page": self.page.next_page_number() if self.page.has_next() else None,
                },
            }
        )


class IdsBypassPagination(StandardResultsPagination):
    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get("ids"):
            return None
        return super().paginate_queryset(queryset, request, view)
