from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any

from django.contrib.auth import get_user_model
from PIL import Image
from rest_framework.test import APITestCase

from tests.testenv.filesystem import IsolatedMediaRootMixin
from accounts.models import UserProfile
from library.groups.services import (
    add_book_to_group,
)
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.utils.books import create_file_backed_book
from tests.utils.library_visibility import (
    ensure_public_book_assignment,
    ensure_public_membership,
)
from tests.utils.users import set_user_role


User = get_user_model()


class BaseShelvesAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(
            username="owner",
            password="pw",
            email="o@example.com",
            first_name="Olivia",
            last_name="Owner",
        )
        ensure_public_membership(self.owner)

        self.reader = User.objects.create_user(
            username="reader",
            password="pw",
            email="reader@example.com",
            first_name="Riley",
            last_name="Reader",
        )
        ensure_public_membership(self.reader)
        set_user_role(self.reader, UserProfile.ROLE_READER)

        self.other = User.objects.create_user(
            username="other", password="pw", first_name="Owen", last_name="Other"
        )
        ensure_public_membership(self.other)

        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        self.curator = User.objects.create_user(username="curator", password="pw")
        ensure_public_membership(self.curator)
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.group,
            is_curator=True,
        )

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_public_membership(self.librarian)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)

        self.manager = User.objects.create_user(
            username="manager", password="pw", is_staff=True
        )
        ensure_public_membership(self.manager)
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)

        self.book_in_group = create_file_backed_book(
            title="B1", assign_public=False
        ).book
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.book_public = create_file_backed_book(title="PB", assign_public=False).book
        ensure_public_book_assignment(self.book_public)

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        self.book_hidden = create_file_backed_book(title="HB", assign_public=False).book
        add_book_to_group(
            actor=self.owner, book=self.book_hidden, group=self.hidden_group
        )

    def _assert_compact_user_payload(
        self,
        payload: Mapping[str, Any],
        *,
        user,
    ) -> None:
        profile, _created = UserProfile.objects.get_or_create(user=user)
        self.assertEqual(payload["profile_id"], profile.id)
        self.assertEqual(payload["username"], user.get_username())
        self.assertEqual(payload["first_name"], user.first_name or "")
        self.assertEqual(payload["last_name"], user.last_name or "")
        self.assertNotIn("id", payload)
        self.assertNotIn("email", payload)

    def _png_bytes(self, *, size=(12, 16)) -> bytes:
        img = Image.new("RGB", size, color=(1, 2, 3))
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
