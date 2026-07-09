from __future__ import annotations

from rest_framework.generics import ListAPIView, RetrieveAPIView

from library.groups.querysets import (
    apply_group_ordering,
    apply_group_search,
    parse_group_ordering,
)
from library.groups.serializers import LibraryGroupSerializer
from library.queries import visible_groups_for_user


class LibraryGroupListView(ListAPIView):
    serializer_class = LibraryGroupSerializer

    def get_queryset(self):
        queryset = visible_groups_for_user(self.request.user)
        queryset = apply_group_search(queryset, self.request.query_params)
        return apply_group_ordering(queryset, parse_group_ordering(self.request))


class LibraryGroupDetailView(RetrieveAPIView):
    serializer_class = LibraryGroupSerializer
    lookup_url_kwarg = "group_id"

    def get_queryset(self):
        return visible_groups_for_user(self.request.user)
