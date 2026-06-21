from __future__ import annotations

from django.conf import settings
from django.contrib.staticfiles.management.commands.runserver import (
    Command as RunserverCommand,
)
from django.core.management import call_command
from django.core.management.base import CommandError


class Command(RunserverCommand):
    help = "Apply migrations, then start Django's development server (DEV ONLY)."

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "--force",
            action="store_true",
            help="Allow running when DEBUG is False.",
        )

    def handle(self, *args, **options):
        force = bool(options.pop("force", False))
        if not getattr(settings, "DEBUG", False) and not force:
            raise CommandError(
                "Refusing to run because DEBUG is False. "
                "Use runserver for production-like environments, or --force "
                "only when you explicitly intend to use this development helper."
            )

        self.stdout.write("Applying pending database migrations...")
        call_command(
            "migrate",
            interactive=False,
            verbosity=int(options.get("verbosity", 1)),
        )
        self.stdout.write("Starting development server...")
        return super().handle(*args, **options)
