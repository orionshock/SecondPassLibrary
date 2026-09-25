from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest import skipUnless
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db import connection
from django.test import TestCase, TransactionTestCase

from accounts.first_owner_setup import (
    FIRST_OWNER_SETUP_GUARD_KEY,
    SetupAlreadyComplete,
    create_first_owner,
)
from accounts.models import UserProfile
from core import server_settings
from core.models import ServerSetting
from core.server_settings import clear_server_settings_cache
from library.groups.public_group import get_public_group
from library.models import LibraryGroup, LibraryGroupMembership
from tests.testenv.database_connections import orm_worker_connection_scope


User = get_user_model()


@skipUnless(connection.vendor == "sqlite", "SQLite concurrency regression")
class FirstOwnerSetupConcurrencyTests(TransactionTestCase):
    reset_sequences = True
    serialized_rollback = True

    def setUp(self):
        cache.clear()
        clear_server_settings_cache()

    def test_concurrent_setup_attempts_create_exactly_one_complete_owner(self):
        barrier = Barrier(2)
        attempts = {
            "alpha": {
                "username": "owner-alpha",
                "password": "Correct-Horse-Battery-Alpha-47",
                "server_name": "Alpha Library",
                "server_description": "Configured by alpha.",
                "public_group_name": "Alpha Room",
                "public_group_description": "Alpha public collection.",
                "advanced_library_groups_enabled": False,
            },
            "beta": {
                "username": "owner-beta",
                "password": "Correct-Horse-Battery-Beta-48",
                "server_name": "Beta Library",
                "server_description": "Configured by beta.",
                "public_group_name": "Beta Room",
                "public_group_description": "Beta public collection.",
                "advanced_library_groups_enabled": True,
            },
        }

        def execute(label: str) -> tuple[str, str]:
            with orm_worker_connection_scope():
                barrier.wait(timeout=5)
                try:
                    owner = create_first_owner(**attempts[label])
                except SetupAlreadyComplete:
                    return label, "lost"
                return label, f"won:{owner.pk}"

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(execute, attempts))

        winners = [label for label, outcome in results if outcome.startswith("won:")]
        losers = [label for label, outcome in results if outcome == "lost"]
        self.assertEqual(len(winners), 1)
        self.assertEqual(len(losers), 1)

        winner = winners[0]
        loser = losers[0]
        winner_input = attempts[winner]
        clear_server_settings_cache()
        public_group = get_public_group()
        owner = User.objects.get(is_active=True, is_superuser=True)

        self.assertEqual(User.objects.filter(is_active=True, is_superuser=True).count(), 1)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(owner.username, winner_input["username"])
        self.assertFalse(User.objects.filter(username=attempts[loser]["username"]).exists())
        self.assertEqual(UserProfile.objects.filter(user=owner).count(), 1)
        self.assertEqual(LibraryGroup.objects.count(), 1)
        self.assertEqual(public_group.name, winner_input["public_group_name"])
        self.assertEqual(
            public_group.description,
            winner_input["public_group_description"],
        )
        self.assertEqual(
            LibraryGroupMembership.objects.filter(
                user=owner,
                group=public_group,
                is_curator=False,
            ).count(),
            1,
        )
        self.assertEqual(server_settings.get_server_name(), winner_input["server_name"])
        self.assertEqual(
            server_settings.get_server_description(),
            winner_input["server_description"],
        )
        self.assertEqual(
            server_settings.get_advanced_library_groups_enabled(),
            winner_input["advanced_library_groups_enabled"],
        )
        self.assertFalse(
            ServerSetting.objects.filter(key=FIRST_OWNER_SETUP_GUARD_KEY).exists()
        )


class SetupLosingRaceResponseTests(TestCase):
    @patch("web.views.create_first_owner", side_effect=SetupAlreadyComplete)
    def test_losing_setup_request_redirects_to_login(self, _create_first_owner):
        response = self.client.post(
            "/setup/",
            {
                "server_name": "Second Pass Library",
                "server_description": "",
                "public_group_name": "Common Room",
                "public_group_description": "Books for everyone.",
                "username": "owner",
                "first_name": "",
                "last_name": "",
                "email": "",
                "password1": "Correct-Horse-Battery-47",
                "password2": "Correct-Horse-Battery-47",
            },
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/login/")
        self.assertFalse(User.objects.filter(is_superuser=True).exists())
