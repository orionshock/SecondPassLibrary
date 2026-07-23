from __future__ import annotations

from rest_framework.pagination import PageNumberPagination


class DefaultPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_query_param = "page"
    page_size_query_param = "page_size"
    max_page_size = 200

    def get_page_size(self, request):
        """
        Parse page_size, falling back to the default on invalid input.

        DRF's default behavior returns None (disabling pagination) when the
        page_size query param is present but invalid. For product APIs, we
        prefer a stable default page size instead.
        """
        if not self.page_size_query_param:
            return self.page_size

        raw = request.query_params.get(self.page_size_query_param)
        if raw is None or raw == "":
            return self.page_size

        try:
            value = int(raw)
        except (TypeError, ValueError):
            return self.page_size

        if value <= 0:
            return self.page_size

        return min(value, self.max_page_size or value)
