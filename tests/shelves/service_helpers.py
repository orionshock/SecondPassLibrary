from __future__ import annotations

from django.contrib.auth import get_user_model

from accounts.models import UserProfile
from library.groups.public_group import get_public_group
from library.groups.services import add_book_to_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import (
    ensure_public_book_assignment,
    ensure_public_membership,
)
from tests.utils.users import set_user_role


User = get_user_model()


class ShelfServiceFixtureMixin(IsolatedMediaRootMixin):
    def setUp(self):
        super().setUp()
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(
            username="owner", password="pw", email="o@example.com"
        )
        ensure_public_membership(self.owner)

        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_public_membership(self.reader)
        set_user_role(self.reader, UserProfile.ROLE_READER)

        self.other = User.objects.create_user(username="other", password="pw")
        ensure_public_membership(self.other)

        self.group = LibraryGroup.objects.create(name="Fantasy Club")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        self.curated_group = LibraryGroup.objects.create(name="Curated")
        self.curator = User.objects.create_user(username="curator", password="pw")
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.curated_group,
            is_curator=True,
        )

        self.book_in_group = create_file_backed_book(
            title="GBook", assign_public=False
        ).book
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.book_other = create_file_backed_book(
            title="OtherBook", assign_public=False
        ).book
        ensure_public_book_assignment(self.book_other)
