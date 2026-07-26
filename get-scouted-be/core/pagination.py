"""Shared DRF pagination for the Phase 7 read layer (CRUD-01, CRUD-05).

Not wired as a project-wide DEFAULT_PAGINATION_CLASS — that would retroactively
paginate every existing ListAPIView (e.g. Phase 2's /api/v1/auth/admin/users/,
which returns a plain list). Instead, each Phase 7 list view sets
`pagination_class` explicitly.

StandardResultsPagination: 25 rows/page, client-adjustable via ?page_size=,
hard-capped at 100 so no caller can request an unbounded page across the
41,708-player table.

IdsBypassPagination is used by the list views' `pagination_class`: when the
caller passes ?ids=<uuid>,<uuid>,... (CRUD-05 multi-fetch) they have already
named an exact, bounded set, so the response is returned unpaginated rather
than forcing a page-2 round-trip for a 3-5 item comparison. Returning None
from paginate_queryset is DRF's documented "do not paginate this response"
signal that ListModelMixin.list() checks for.
"""

from rest_framework.pagination import PageNumberPagination


class StandardResultsPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 100


class IdsBypassPagination(StandardResultsPagination):
    def paginate_queryset(self, queryset, request, view=None):
        if request.query_params.get("ids"):
            return None
        return super().paginate_queryset(queryset, request, view)
