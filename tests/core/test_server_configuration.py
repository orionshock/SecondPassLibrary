from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from core import server_settings
from core.models import ServerSetting
from core.rich_text import DESCRIPTIVE_PROSE_MAX_LENGTH
from core.server_configuration import update_owner_server_configuration
from library.groups.public_group import get_public_group
from library.models import Book, BookGroupAssignment, LibraryGroupMembership
from shelves.models import Shelf


User = get_user_model()


class OwnerServerConfigurationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.public_group = get_public_group()
        server_settings.set_server_name("Original Library")
        self.client.force_login(self.owner)

    def test_mixed_valid_and_invalid_api_patch_does_not_partially_persist(self):
        original_group_name = self.public_group.name

        response = self.client.patch(
            "/api/v1/server/settings/",
            data={
                "server_name": "Must Roll Back",
                "public_group_name": "Must Also Roll Back",
                "public_group_description": "x"
                * (DESCRIPTIVE_PROSE_MAX_LENGTH + 1),
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("public_group_description", response.json())
        self.assertEqual(
            ServerSetting.objects.get(key=server_settings.SERVER_NAME_SETTING).value,
            "Original Library",
        )
        self.public_group.refresh_from_db()
        self.assertEqual(self.public_group.name, original_group_name)
        projection = self.client.get("/api/v1/server/settings/").json()
        self.assertEqual(projection["server_name"], "Original Library")
        self.assertEqual(projection["public_group_name"], original_group_name)

    def test_multi_domain_patch_preserves_public_group_identity_and_relationships(self):
        member = User.objects.create_user(username="reader", password="pw")
        membership = LibraryGroupMembership.objects.create(
            user=member,
            group=self.public_group,
        )
        book = Book.objects.create(title="Assigned")
        assignment = BookGroupAssignment.objects.create(
            book=book,
            group=self.public_group,
            added_by=self.owner,
        )
        shelf = Shelf.objects.create(
            name="Public Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=self.public_group,
            created_by=self.owner,
        )
        group_id = self.public_group.pk

        result = update_owner_server_configuration(
            patch={
                "server_name": "Committed Library",
                "second_pass_reader_web_client_url": "https://reader.example/app",
                "public_group_name": "Reading Room",
                "public_group_description": "Shared books.",
            },
            actor=self.owner,
        )

        self.public_group.refresh_from_db()
        self.assertEqual(self.public_group.pk, group_id)
        self.assertEqual(self.public_group.name, "Reading Room")
        self.assertTrue(LibraryGroupMembership.objects.filter(pk=membership.pk).exists())
        self.assertTrue(BookGroupAssignment.objects.filter(pk=assignment.pk).exists())
        self.assertTrue(Shelf.objects.filter(pk=shelf.pk, owner_group_id=group_id).exists())
        self.assertEqual(result["server_name"], "Committed Library")
        self.assertEqual(
            result["second_pass_reader_web_client_url"],
            "https://reader.example",
        )

    def test_public_group_failure_keeps_committed_settings_visible(self):
        original_group_name = self.public_group.name

        with (
            patch(
                "core.server_configuration.configure_public_group",
                side_effect=RuntimeError("injected failure"),
            ),
            self.assertLogs("core.server_configuration", level="ERROR"),
            self.captureOnCommitCallbacks(execute=True),
            self.assertRaises(RuntimeError),
        ):
            update_owner_server_configuration(
                patch={
                    "server_name": "Must Roll Back",
                    "public_group_name": "Must Roll Back",
                },
                actor=self.owner,
            )

        self.assertEqual(
            ServerSetting.objects.get(key=server_settings.SERVER_NAME_SETTING).value,
            "Original Library",
        )
        self.public_group.refresh_from_db()
        self.assertEqual(self.public_group.name, original_group_name)
        self.assertEqual(server_settings.get_server_name(), "Original Library")

    def test_partial_patch_retains_omitted_values(self):
        server_settings.set_server_description("Original description.")
        original_group_name = self.public_group.name

        result = update_owner_server_configuration(
            patch={"server_banner_message": "Maintenance tonight."},
            actor=self.owner,
        )

        self.assertEqual(result["server_name"], "Original Library")
        self.assertEqual(result["server_description"], "Original description.")
        self.assertEqual(result["server_banner_message"], "Maintenance tonight.")
        self.assertEqual(result["public_group_name"], original_group_name)

    def test_successful_multi_setting_update_publishes_complete_state(self):
        with self.captureOnCommitCallbacks(execute=True):
            update_owner_server_configuration(
                patch={
                    "server_name": "Committed Library",
                    "server_description": "Committed description.",
                    "server_banner_message": "Committed banner.",
                },
                actor=self.owner,
            )

        self.assertEqual(server_settings.get_server_name(), "Committed Library")
        self.assertEqual(
            server_settings.get_server_description(),
            "Committed description.",
        )
        self.assertEqual(
            server_settings.get_server_banner_message(),
            "Committed banner.",
        )
