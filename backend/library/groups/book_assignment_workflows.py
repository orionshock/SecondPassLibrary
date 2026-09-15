from __future__ import annotations

from django.db import transaction
from django.http import Http404
from rest_framework.exceptions import PermissionDenied

from accounts.roles import is_librarian
from library.groups.api_access import normal_book_assignment_group_or_404
from library.groups.book_assignments import add_book_to_group, remove_book_from_group
from library.models import Book, BookGroupAssignment
from library.queries import visible_books_for_user
from library.roles import is_curator


def create_normal_book_assignment(*, actor, group_id, book_id) -> BookGroupAssignment:
    with transaction.atomic():
        group = normal_book_assignment_group_or_404(
            actor=actor,
            group_id=group_id,
        )
        book = _visible_book_or_404(actor=actor, book_id=book_id)
        if not is_librarian(actor) and not is_curator(actor, group):
            raise PermissionDenied("Not allowed to add books to this group.")
        return add_book_to_group(book=book, group=group, actor=actor)


def remove_normal_book_assignment(*, actor, group_id, book_id) -> bool:
    with transaction.atomic():
        group = normal_book_assignment_group_or_404(
            actor=actor,
            group_id=group_id,
        )
        book = _visible_book_or_404(actor=actor, book_id=book_id)
        if not is_curator(actor, group):
            raise PermissionDenied("Not allowed to remove books from this group.")
        return remove_book_from_group(book=book, group=group, actor=actor)


def _visible_book_or_404(*, actor, book_id) -> Book:
    try:
        book = Book.objects.get(pk=book_id)
    except Book.DoesNotExist as exc:
        raise Http404 from exc
    if is_librarian(actor):
        return book
    if not visible_books_for_user(actor, cached=False).filter(pk=book.pk).exists():
        raise Http404
    return book
