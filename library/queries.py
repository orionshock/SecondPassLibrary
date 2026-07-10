from __future__ import annotations

from collections.abc import Iterable

from django.core.cache import cache
from django.db.models import QuerySet

from accounts.roles import is_librarian

from .models import Book, LibraryGroup, LibraryGroupMembership


VISIBLE_BOOK_IDS_CACHE_SECONDS = 120


def can_manage_library(user) -> bool:
    return is_librarian(user)


def effective_group_ids_for_user(user) -> QuerySet:
    if user is None or getattr(user, "is_anonymous", False):
        return LibraryGroupMembership.objects.none().values_list("group_id", flat=True)
    return LibraryGroupMembership.objects.filter(user=user).values_list("group_id", flat=True)


def can_view_group(*, user, group: LibraryGroup) -> bool:
    if can_manage_library(user):
        return True
    if user is None or getattr(user, "is_anonymous", False):
        return False
    return LibraryGroupMembership.objects.filter(user=user, group=group).exists()


def visible_groups_for_user(user) -> QuerySet[LibraryGroup]:
    if can_manage_library(user):
        return LibraryGroup.objects.all()
    if user is None or getattr(user, "is_anonymous", False):
        return LibraryGroup.objects.none()
    return LibraryGroup.objects.filter(memberships__user=user).distinct()


def _visible_book_ids_cache_key(user) -> str:
    return f"libraryrewrite2607:visible-book-ids:user:{getattr(user, 'pk', 'anonymous')}"


def _book_ids(queryset: QuerySet[Book]) -> list[str]:
    return [str(pk) for pk in queryset.values_list("pk", flat=True)]


def _books_by_ids(ids: Iterable[str]) -> QuerySet[Book]:
    return Book.objects.filter(pk__in=list(ids)).distinct()


def _visible_books_for_user_uncached(user) -> QuerySet[Book]:
    if can_manage_library(user):
        return Book.objects.all()
    if user is None or getattr(user, "is_anonymous", False):
        return Book.objects.none()
    return Book.objects.filter(
        group_assignments__group_id__in=effective_group_ids_for_user(user)
    ).distinct()


def visible_books_for_user(user, cached: bool = True) -> QuerySet[Book]:
    """
    Return the global library universe visible to a user.

    Cached results are for browse/read lists only. Authorization-sensitive paths
    should call with cached=False.
    """
    if not cached:
        return _visible_books_for_user_uncached(user)

    key = _visible_book_ids_cache_key(user)
    ids = cache.get(key)
    if ids is None:
        ids = _book_ids(_visible_books_for_user_uncached(user))
        cache.set(key, ids, VISIBLE_BOOK_IDS_CACHE_SECONDS)
    return _books_by_ids(ids)


def visible_books_for_group(user, group: LibraryGroup, cached: bool = True) -> QuerySet[Book]:
    """
    Return books assigned to a group after confirming the user can see the group.
    """
    if not can_view_group(user=user, group=group):
        return Book.objects.none()

    base = visible_books_for_user(user, cached=cached)
    return base.filter(group_assignments__group=group).distinct()
