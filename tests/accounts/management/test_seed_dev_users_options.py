from __future__ import annotations

from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings

from shelves.models import Shelf, ShelfItem
from tests.accounts.management.helpers import SeedDevUsersCommandTestCase, User


class SeedDevUsersOptionsTests(SeedDevUsersCommandTestCase):
    @override_settings(DEBUG=False)
    def test_refuses_when_debug_false_unless_forced(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command"
        ) as migrate_command:
            with self.assertRaises(CommandError):
                call_command("seed_dev_users")
        migrate_command.assert_not_called()

        self.create_setup_owner()
        call_command(
            "seed_dev_users",
            force=True,
            users=1,
            groups=1,
            skip_shelves=True,
            verbosity=0,
        )

        self.assertTrue(User.objects.filter(username="lorem").exists())

    @override_settings(DEBUG=True)
    def test_requires_first_run_setup_owner(self):
        with patch(
            "accounts.management.commands.seed_dev_users.call_command"
        ) as migrate_command:
            with self.assertRaises(CommandError) as cm:
                call_command("seed_dev_users", verbosity=0)

        self.assertIn("Complete setup before running seed_dev_users", str(cm.exception))
        migrate_command.assert_not_called()
        self.assertFalse(User.objects.filter(username="lorem-admin").exists())

    @override_settings(DEBUG=True)
    def test_applies_migrations_before_seeding(self):
        self.create_setup_owner()
        with patch(
            "accounts.management.commands.seed_dev_users.call_command",
            wraps=call_command,
        ) as migrate_command:
            call_command(
                "seed_dev_users",
                users=1,
                groups=1,
                skip_shelves=True,
                verbosity=0,
            )

        migrate_command.assert_called_once_with(
            "migrate",
            interactive=False,
            verbosity=0,
        )

    @override_settings(DEBUG=True)
    def test_skip_shelves_skips_creation_and_population(self):
        self.create_setup_owner()
        output = StringIO()

        call_command(
            "seed_dev_users",
            users=3,
            groups=2,
            skip_shelves=True,
            verbosity=0,
            stdout=output,
        )

        self.assertFalse(Shelf.objects.exists())
        self.assertFalse(ShelfItem.objects.exists())
        self.assertIn("Shelves: skipped by --skip-shelves.", output.getvalue())
