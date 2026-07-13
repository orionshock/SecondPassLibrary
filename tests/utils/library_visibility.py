from __future__ import annotations

from uuid import uuid4

from django.contrib.auth import get_user_model

from library.groups.memberships import ensure_user_public_membership
from library.groups.book_assignments import add_book_to_group, ensure_book_public_assignment
from library.models import LibraryGroup, LibraryGroupMembership
from tests.utils.books import create_file_backed_book


User = get_user_model()


def ensure_public_membership(user):
    return ensure_user_public_membership(user=user)


def ensure_public_book_assignment(book, *, actor=None):
    return ensure_book_public_assignment(book=book, added_by=actor)


def make_visible_book_for_user(
    user, *, title: str = "Visible Book", actor=None, **book_options
):
    ensure_public_membership(user)
    created = create_file_backed_book(title=title, assign_public=False, **book_options)
    ensure_public_book_assignment(created.book, actor=actor)
    return created.book


def make_hidden_book_for_user(user, *, title: str = "Hidden Book", actor=None, **book_options):
    group = LibraryGroup.objects.create(name=f"{title} Group")
    username = f"{title.lower().replace(' ', '-')}-owner-{uuid4().hex[:8]}"
    owner = actor or User.objects.create_superuser(
        username=username,
        password="pw",
        email=f"{username}@example.com",
    )
    created = create_file_backed_book(title=title, assign_public=False, **book_options)
    add_book_to_group(actor=owner, book=created.book, group=group)
    return created.book


def make_group_with_member(
    user, *, name: str = "Test Group", is_curator: bool = False
) -> LibraryGroup:
    group = LibraryGroup.objects.create(name=name)
    LibraryGroupMembership.objects.create(user=user, group=group, is_curator=is_curator)
    return group
