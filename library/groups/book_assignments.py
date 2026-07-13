from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from core.operational_logging import info_on_commit, user_uuid
from library.groups.public_group import get_public_group
from library.models import Book, BookGroupAssignment, LibraryGroup
from library.queries import invalidate_visible_books_cache
from shelves.library_hooks import remove_book_from_group_owned_shelves


logger = logging.getLogger(__name__)


def add_book_to_group(
    *, book, group: LibraryGroup, actor=None, added_by=None
) -> BookGroupAssignment:
    if group is None:
        raise ValidationError("Group is required.")
    creator = added_by if added_by is not None else actor
    with transaction.atomic():
        book = _lock_book_for_group_assignment(book)
        assignment, created = _create_book_assignment(
            book=book,
            group=group,
            added_by=creator,
        )
    if created:
        info_on_commit(
            logger,
            "Book assigned to library group: actor=%s added_by=%s book=%s group=%s",
            user_uuid(actor),
            user_uuid(creator),
            book.pk,
            group.pk,
        )
    return assignment


def remove_book_from_group(*, book, group: LibraryGroup, actor=None) -> bool:
    with transaction.atomic():
        book = _lock_book_for_group_assignment(book)
        if BookGroupAssignment.objects.filter(book=book, group=group).exists():
            remove_book_from_group_owned_shelves(book=book, group=group)
        deleted, _ = BookGroupAssignment.objects.filter(book=book, group=group).delete()
        restored = _ensure_book_has_at_least_one_group_locked(book=book, added_by=actor)
        if deleted and not restored:
            _invalidate_visible_books_cache_on_commit()
    if deleted:
        info_on_commit(
            logger,
            "Book removed from library group: actor=%s book=%s group=%s fallback_to_public=%s",
            user_uuid(actor),
            book.pk,
            group.pk,
            bool(restored),
        )
    return bool(deleted)


def ensure_book_public_assignment(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> BookGroupAssignment:
    with transaction.atomic():
        book = _lock_book_for_group_assignment(book)
        return _ensure_book_public_assignment_locked(
            book=book,
            added_by=added_by,
            public_group=public_group,
        )


def _ensure_book_public_assignment_locked(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> BookGroupAssignment:
    group = public_group or get_public_group()
    assignment, created = _create_book_assignment(book=book, group=group, added_by=added_by)
    if created:
        info_on_commit(
            logger,
            "Book assigned to library group: actor=%s added_by=%s book=%s group=%s",
            "none",
            user_uuid(added_by),
            book.pk,
            group.pk,
        )
    return assignment


def ensure_book_has_at_least_one_group(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> bool:
    with transaction.atomic():
        book = _lock_book_for_group_assignment(book)
        return _ensure_book_has_at_least_one_group_locked(
            book=book,
            added_by=added_by,
            public_group=public_group,
        )


def _ensure_book_has_at_least_one_group_locked(
    *, book, added_by=None, public_group: LibraryGroup | None = None
) -> bool:
    if not BookGroupAssignment.objects.filter(book=book).exists():
        _ensure_book_public_assignment_locked(
            book=book, added_by=added_by, public_group=public_group
        )
        return True
    return False


def _restore_books_without_groups(
    book_ids: list, *, added_by=None, public_group: LibraryGroup | None = None
) -> int:
    restored = 0
    locked_book_ids = list(
        Book.objects.select_for_update()
        .filter(pk__in=book_ids)
        .values_list("pk", flat=True)
    )
    for book_id in locked_book_ids:
        if not BookGroupAssignment.objects.filter(book_id=book_id).exists():
            group = public_group or get_public_group()
            BookGroupAssignment.objects.get_or_create(
                book_id=book_id,
                group=group,
                defaults={"added_by": added_by},
            )
            restored += 1
    return restored


def _create_book_assignment(
    *, book, group: LibraryGroup, added_by=None
) -> tuple[BookGroupAssignment, bool]:
    assignment, created = BookGroupAssignment.objects.get_or_create(
        book=book,
        group=group,
        defaults={"added_by": added_by},
    )
    if created:
        _invalidate_visible_books_cache_on_commit()
    return assignment, created


def _lock_book_for_group_assignment(book):
    return Book.objects.select_for_update().get(pk=book.pk)


def _invalidate_visible_books_cache_on_commit() -> None:
    transaction.on_commit(invalidate_visible_books_cache)
