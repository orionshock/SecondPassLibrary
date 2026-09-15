from __future__ import annotations

from rest_framework.response import Response

from library.catalog.serializers.axes import CatalogTagAxisSerializer
from library.catalog.tag_aggregates import catalog_tag_aggregates


class CatalogTagAggregateBookListMixin:
    """Keep result-set tag aggregates independent of the paginated Book page."""

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        catalog_tags = CatalogTagAxisSerializer(
            catalog_tag_aggregates(queryset), many=True
        ).data
        page = self.paginate_queryset(queryset)
        if page is not None:
            response = self.get_paginated_response(
                self.get_serializer(page, many=True).data
            )
            response.data["catalog_tags"] = catalog_tags
            return response
        return Response(
            {
                "catalog_tags": catalog_tags,
                "results": self.get_serializer(queryset, many=True).data,
            }
        )
