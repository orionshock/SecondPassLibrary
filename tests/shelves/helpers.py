from __future__ import annotations

from collections.abc import Mapping
from io import BytesIO
from typing import Any

from django.contrib.auth import get_user_model
from PIL import Image
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.groups.services import (
    add_book_to_group,
    ensure_book_public_assignment,
    ensure_user_public_membership,
)
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.utils.books import create_file_backed_book


User = get_user_model()


class BaseShelvesAPITest(APITestCase):
    def setUp(self):
        self.public = get_public_group()

        self.owner = User.objects.create_superuser(
            username="owner",
            password="pw",
            email="o@example.com",
            first_name="Olivia",
            last_name="Owner",
        )
        ensure_user_public_membership(user=self.owner)

        self.reader = User.objects.create_user(
            username="reader",
            password="pw",
            email="reader@example.com",
            first_name="Riley",
            last_name="Reader",
        )
        ensure_user_public_membership(user=self.reader)
        profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        profile.role = UserProfile.ROLE_READER
        profile.save(update_fields=["role", "updated_at"])

        self.other = User.objects.create_user(
            username="other", password="pw", first_name="Owen", last_name="Other"
        )
        ensure_user_public_membership(user=self.other)

        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(user=self.reader, group=self.group)
        self.curator = User.objects.create_user(username="curator", password="pw")
        ensure_user_public_membership(user=self.curator)
        LibraryGroupMembership.objects.create(
            user=self.curator,
            group=self.group,
            is_curator=True,
        )

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(
            username="manager", password="pw", is_staff=True
        )
        ensure_user_public_membership(user=self.manager)
        profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        profile.role = UserProfile.ROLE_MANAGER
        profile.save(update_fields=["role", "updated_at"])

        self.book_in_group = create_file_backed_book(
            title="B1", assign_public=False
        ).book
        add_book_to_group(actor=self.owner, book=self.book_in_group, group=self.group)

        self.book_public = create_file_backed_book(title="PB", assign_public=False).book
        ensure_book_public_assignment(book=self.book_public, added_by=None)

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
