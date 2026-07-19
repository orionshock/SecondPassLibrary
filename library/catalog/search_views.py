from __future__ import annotations

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Q
from django.http import Http404
from rest_framework.generics import ListAPIView

from library.api_access import LibraryBearerReadMixin
from library.catalog.ordering import apply_book_ordering, parse_ordering_param
from library.catalog.serializers import BookListSerializer
from library.catalog.views import book_browse_queryset
from library.groups.api_access import groups_available_via_api
from library.models import LibraryGroup
from library.queries import group_is_visible_to_user, visible_books_for_user
from library.roles import is_curator
from shelves.models import Shelf
from shelves.querysets import visible_shelf_filter
from shelves.services import can_edit_shelf


SEARCH_ORDERINGS = {"title", "-title", "author", "-author", "series", "-series"}


class UserBookVerseSearchView(LibraryBearerReadMixin, ListAPIView):
    serializer_class = BookListSerializer

    def get_queryset(self):
        queryset = visible_books_for_user(self.request.user, cached=False)
        term = str(self.request.query_params.get("q") or "").strip()
        if not term:
            queryset = queryset.none()
        else:
            queryset = queryset.filter(
                Q(title__icontains=term)
                | Q(sort_title__icontains=term)
                | Q(subtitle__icontains=term)
                | Q(book_authors__author__name__icontains=term)
                | Q(book_series__series__name__icontains=term)
                | Q(identifiers__value__icontains=term)
                | Q(book_catalog_tags__catalog_tag__name__icontains=term)
                | Q(publisher__icontains=term)
                | Q(description__icontains=term)
            ).distinct()

        queryset = _exclude_shelf_books(
            queryset,
            user=self.request.user,
            raw_shelf_id=self.request.query_params.get("exclude_shelf", ""),
        )
        queryset = _exclude_group_books(
            queryset,
            user=self.request.user,
            raw_group_id=self.request.query_params.get("exclude_group", ""),
        )
        queryset = book_browse_queryset(queryset)
        ordering = parse_ordering_param(
            self.request,
            allowed=SEARCH_ORDERINGS,
            default="title",
        )
        return apply_book_ordering(queryset, ordering)


def _exclude_shelf_books(queryset, *, user, raw_shelf_id: str):
    shelf_id = _uuid_or_404(Shelf, raw_shelf_id)
    if shelf_id is None:
        return queryset
    shelf = (
        Shelf.objects.filter(visible_shelf_filter(user), pk=shelf_id)
        .select_related("owner_group", "owner_user")
        .first()
    )
    if shelf is None or not can_edit_shelf(user=user, shelf=shelf):
        raise Http404
    return queryset.exclude(shelf_items__shelf=shelf)


def _exclude_group_books(queryset, *, user, raw_group_id: str):
    group_id = _uuid_or_404(LibraryGroup, raw_group_id)
    if group_id is None:
        return queryset
    group = groups_available_via_api(LibraryGroup.objects.all()).filter(pk=group_id).first()
    if (
        group is None
        or not group_is_visible_to_user(user=user, group=group)
        or not is_curator(user, group)
    ):
        raise Http404
    return queryset.exclude(group_assignments__group=group)


def _uuid_or_404(model, raw_value: str):
    value = str(raw_value or "").strip()
    if not value:
        return None
    try:
        return model._meta.pk.to_python(value)
    except (ValueError, DjangoValidationError) as exc:
        raise Http404 from exc
