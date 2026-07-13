from __future__ import annotations

import logging

from django.core.exceptions import ValidationError
from django.db import transaction

from core.operational_logging import info_on_commit, safe_log_label, user_log_label
from library.groups.public_group import get_public_group
from library.models import Book, BookGroupAssignment, LibraryGroup
from library.queries import invalidate_visible_books_cache_on_commit
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
        book_id, book_title, group_id, group_name = _assignment_log_values(
            book=book,
            group=group,
        )
        actor_name = user_log_label(actor)
        creator_name = user_log_label(creator)
        if creator is not None and creator != actor:
            info_on_commit(
                logger,
                "Book assigned to library group: book_title=%s book=%s group_name=%s "
                "group=%s actor=%s added_by=%s",
                book_title,
                book_id,
                group_name,
                group_id,
                actor_name,
                creator_name,
            )
        else:
            info_on_commit(
                logger,
                "Book assigned to library group: book_title=%s book=%s group_name=%s "
                "group=%s actor=%s",
                book_title,
                book_id,
                group_name,
                group_id,
                actor_name,
            )
    return assignment


def remove_book_from_group(*, book, group: LibraryGroup, actor=None) -> bool:
    with transaction.atomic():
        book = _lock_book_for_group_assignment(book)
        book_id, book_title, group_id, group_name = _assignment_log_values(
            book=book,
            group=group,
        )
        actor_name = user_log_label(actor)
        if BookGroupAssignment.objects.filter(book=book, group=group).exists():
            remove_book_from_group_owned_shelves(book=book, group=group)
        deleted, _ = BookGroupAssignment.objects.filter(book=book, group=group).delete()
        restored = _ensure_book_has_at_least_one_group_locked(book=book, added_by=actor)
        if deleted and not restored:
            invalidate_visible_books_cache_on_commit()
    if deleted:
        info_on_commit(
            logger,
            "Book removed from library group: book_title=%s book=%s group_name=%s "
            "group=%s actor=%s fallback_to_public=%s",
            book_title,
            book_id,
            group_name,
            group_id,
            actor_name,
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
        book_id, book_title, group_id, group_name = _assignment_log_values(
            book=book,
            group=group,
        )
        if added_by is not None:
            added_by_name = user_log_label(added_by)
            info_on_commit(
                logger,
                "Book assigned to library group: book_title=%s book=%s group_name=%s "
                "group=%s actor=none added_by=%s",
                book_title,
                book_id,
                group_name,
                group_id,
                added_by_name,
            )
        else:
            info_on_commit(
                logger,
                "Book assigned to library group: book_title=%s book=%s group_name=%s "
                "group=%s actor=none",
                book_title,
                book_id,
                group_name,
                group_id,
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


def restore_selected_books_without_groups(
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
        invalidate_visible_books_cache_on_commit()
    return assignment, created


def _lock_book_for_group_assignment(book):
    return Book.objects.select_for_update().get(pk=book.pk)


def _assignment_log_values(*, book, group) -> tuple[str, str, str, str]:
    book_id = str(book.pk)
    group_id = str(group.pk)
    return (
        book_id,
        safe_log_label(book.title, fallback=book_id),
        group_id,
        safe_log_label(group.name, fallback=group_id),
    )
