from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from accounts.models import UserProfile
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.helpers import set_user_role


def json_body(data: dict) -> str:
    return json.dumps(data)


class LibraryGroupBookAssignmentApiTestCase(TestCase):
    def setUp(self):
        cache.clear()
        User = get_user_model()
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.curator = User.objects.create_user(username="curator", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        for user in [self.reader, self.curator]:
            set_user_role(user, UserProfile.ROLE_READER)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.club = LibraryGroup.objects.create(name="Club")
        self.source = LibraryGroup.objects.create(name="Source")
        self.hidden = LibraryGroup.objects.create(name="Hidden")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)
        LibraryGroupMembership.objects.create(user=self.curator, group=self.club, is_curator=True)
        LibraryGroupMembership.objects.create(user=self.curator, group=self.source)

        self.club_book = Book.objects.create(title="Club Book")
        self.source_book = Book.objects.create(title="Source Book")
        self.hidden_book = Book.objects.create(title="Hidden Book")
        self.extra_hidden_book = Book.objects.create(title="Extra Hidden Book")
        BookGroupAssignment.objects.create(book=self.club_book, group=self.club, added_by=self.owner)
        BookGroupAssignment.objects.create(book=self.source_book, group=self.source)
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.hidden)
        BookGroupAssignment.objects.create(book=self.extra_hidden_book, group=self.hidden)

    def group_books_url(self, group=None) -> str:
        group = group or self.club
        return f"/api/v1/library/groups/{group.id}/books/"

    def group_book_detail_url(self, *, group=None, book=None) -> str:
        group = group or self.club
        book = book or self.club_book
        return f"/api/v1/library/groups/{group.id}/books/{book.id}/"
