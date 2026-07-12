from __future__ import annotations

from typing import Any, cast

from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APITestCase

from accounts.client_api import generate_bearer_token, hash_client_secret
from accounts.models import UserClientSession, UserProfile
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book
from tests.utils.responses import assert_response, response_data_dict
from tests.utils.users import set_user_role


User = get_user_model()


class ShelvesBearerApiTestCase(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="u",
            email="u@example.com",
            password="pw",
            first_name="Uma",
            last_name="User",
        )
        set_user_role(self.user, UserProfile.ROLE_READER)

        self.other = User.objects.create_user(
            username="o", email="o@example.com", password="pw"
        )
        set_user_role(self.other, UserProfile.ROLE_READER)

        token = generate_bearer_token()
        UserClientSession.objects.create(
            user=self.user,
            name="t",
            client_type="test",
            token_hash=hash_client_secret(token),
            last_seen_at=timezone.now(),
        )
        self._auth = f"Bearer {token}"

        self.public_group = get_public_group()
        self.group = LibraryGroup.objects.create(name="G")
        LibraryGroupMembership.objects.create(
            user=self.user, group=self.group, is_curator=True
        )

        self.book_public = create_file_backed_book(
            title="Public book", assign_public=False
        ).book
        cast(Any, self.book_public).group_assignments.create(
            group=self.public_group, added_by=self.user
        )
        self.book_in_group = create_file_backed_book(
            title="Group book", assign_public=False
        ).book
        cast(Any, self.book_in_group).group_assignments.create(
            group=self.group, added_by=self.user
        )

        self.book_hidden = create_file_backed_book(
            title="Hidden", assign_public=False
        ).book
        hidden_group = LibraryGroup.objects.create(name="Hidden")
        cast(Any, self.book_hidden).group_assignments.create(
            group=hidden_group, added_by=self.user
        )

    def _create_personal_shelf_as_owner(self) -> str:
        resp = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={"name": "P", "owner_type": "user"},
                format="json",
                HTTP_AUTHORIZATION=self._auth,
            ),
        )
        self.assertEqual(resp.status_code, 201)
        data = response_data_dict(resp)
        return str(data["id"])

    def _create_group_shelf_with_item_as_session_user(self) -> tuple[str, str]:
        self.client.force_login(self.user)
        created = assert_response(
            self.client.post(
                "/api/v1/shelves/",
                data={
                    "name": "GS",
                    "owner_type": "group",
                    "owner_group": str(self.group.id),
                },
                format="json",
            ),
        )
        self.assertEqual(created.status_code, 201)
        shelf_id = str(response_data_dict(created)["id"])

        added = assert_response(
            self.client.post(
                f"/api/v1/shelves/{shelf_id}/items/",
                data={"book": str(self.book_in_group.id)},
                format="json",
            ),
        )
        self.assertEqual(added.status_code, 201)
        item_id = str(response_data_dict(added)["id"])
        self.client.logout()
        return shelf_id, item_id
