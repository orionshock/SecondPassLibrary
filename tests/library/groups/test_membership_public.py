from __future__ import annotations

from library.models import LibraryGroupMembership
from library.roles import is_curator
from tests.library.groups.membership_helpers import (
    LibraryGroupMembershipApiTestCase,
    json_body,
)


class LibraryPublicMembershipApiTests(LibraryGroupMembershipApiTestCase):
    def test_public_curator_membership_does_not_grant_curation(self):
        LibraryGroupMembership.objects.create(user=self.target, group=self.public)
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            self.membership_detail_url(group=self.public),
            json_body({"is_curator": True}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(is_curator(self.target, self.public))
