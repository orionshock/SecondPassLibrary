from __future__ import annotations

from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings


class DevServerCommandTests(SimpleTestCase):
    @override_settings(DEBUG=False)
    def test_refuses_outside_debug_without_force(self):
        with (
            patch("core.management.commands.devserver.call_command") as migrate,
            patch(
                "core.management.commands.devserver.RunserverCommand.handle"
            ) as runserver,
        ):
            with self.assertRaises(CommandError):
                call_command("devserver", "--noreload", verbosity=0)

        migrate.assert_not_called()
        runserver.assert_not_called()

    @override_settings(DEBUG=True)
    def test_runs_migrate_before_runserver(self):
        calls: list[str] = []

        def record_migrate(*args, **kwargs):
            calls.append("migrate")

        def record_runserver(*args, **kwargs):
            calls.append("runserver")

        with (
            patch(
                "core.management.commands.devserver.call_command",
                side_effect=record_migrate,
            ) as migrate,
            patch(
                "core.management.commands.devserver.RunserverCommand.handle",
                side_effect=record_runserver,
            ) as runserver,
        ):
            call_command("devserver", "--noreload", verbosity=0)

        self.assertEqual(calls, ["migrate", "runserver"])
        migrate.assert_called_once_with(
            "migrate",
            interactive=False,
            verbosity=0,
        )
        runserver.assert_called_once()

    @override_settings(DEBUG=False)
    def test_force_allows_explicit_non_debug_use(self):
        with (
            patch("core.management.commands.devserver.call_command") as migrate,
            patch(
                "core.management.commands.devserver.RunserverCommand.handle",
                return_value=None,
            ) as runserver,
        ):
            call_command("devserver", "--force", "--noreload", verbosity=0)

        migrate.assert_called_once_with(
            "migrate",
            interactive=False,
            verbosity=0,
        )
        runserver.assert_called_once()
