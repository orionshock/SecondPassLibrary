from __future__ import annotations

from typing import Any, cast

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from accounts.models import ExternalIdentity
from tests.utils.responses import assert_response


class ExternalIdentityModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="external-user")

    def test_multiple_external_identities_can_link_to_one_user(self):
        first = ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id.example.test/",
            subject="subject-1",
            email_at_login="reader@example.test",
            email_verified=True,
            selected_claims={"name": "Reader One"},
        )
        second = ExternalIdentity.objects.create(
            user=self.user,
            provider="secondary",
            issuer="https://login.example.test/",
            subject="subject-2",
        )

        self.assertEqual(first.user, self.user)
        self.assertEqual(second.user, self.user)
        self.assertEqual(cast(Any, self.user).external_identities.count(), 2)

    def test_issuer_and_subject_must_be_unique(self):
        ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id.example.test/",
            subject="shared-subject",
        )

        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                ExternalIdentity.objects.create(
                    user=User.objects.create_user(username="other-user"),
                    provider="primary",
                    issuer="https://id.example.test/",
                    subject="shared-subject",
                )

    def test_same_subject_under_different_issuer_is_allowed(self):
        ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id-one.example.test/",
            subject="shared-subject",
        )
        ExternalIdentity.objects.create(
            user=self.user,
            provider="secondary",
            issuer="https://id-two.example.test/",
            subject="shared-subject",
        )
        self.assertEqual(cast(Any, self.user).external_identities.count(), 2)

    def test_external_identities_are_not_exposed_by_account_apis(self):
        ExternalIdentity.objects.create(
            user=self.user,
            provider="primary",
            issuer="https://id.example.test/",
            subject="private-subject",
        )
        self.user.set_password("pw")
        self.user.save(update_fields=["password"])
        self.client.login(username="external-user", password="pw")

        profile_response = assert_response(
            self.client.get("/api/v1/accounts/profiles/")
        )
        self.assertNotContains(profile_response, "private-subject")
        me_response = assert_response(self.client.get("/api/v1/accounts/me/"))
        self.assertNotContains(me_response, "private-subject")
