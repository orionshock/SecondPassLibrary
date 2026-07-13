from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.user_payloads import compact_user_payload


class CompactUserPayloadTests(TestCase):
    def test_compact_user_payload_is_username_only(self):
        user = get_user_model().objects.create_user(
            username="reader",
            email="private@example.test",
            first_name="Read",
            last_name="Er",
            password="pw",
        )

        payload = compact_user_payload(user)

        self.assertEqual(
            set(payload),
            {"profile_id", "username"},
        )
