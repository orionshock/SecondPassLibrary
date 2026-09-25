from __future__ import annotations

import getpass
import sys
from typing import Any, TextIO

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError, CommandParser

from accounts.first_owner_setup import (
    SetupAlreadyComplete,
    create_first_owner,
    has_active_owner,
)
from core.server_settings import DEFAULT_SERVER_NAME
from library.groups.public_group import (
    DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    DEFAULT_PUBLIC_GROUP_NAME,
)


class Command(BaseCommand):
    help = "Initialize a fresh server and create its first Owner."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("--username", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--email", default="")
        parser.add_argument("--server-name", default=DEFAULT_SERVER_NAME)
        parser.add_argument("--server-description", default="")
        parser.add_argument("--public-group-name", default=DEFAULT_PUBLIC_GROUP_NAME)
        parser.add_argument(
            "--public-group-description",
            default=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
        )
        parser.add_argument(
            "--advanced-library-groups-enabled",
            action="store_true",
            help="Enable Advanced Library Groups during setup.",
        )
        password_modes = parser.add_mutually_exclusive_group()
        password_modes.add_argument(
            "--password-stdin",
            action="store_true",
            help=(
                "Read one raw password from stdin and apply normal Django password "
                "validation."
            ),
        )
        password_modes.add_argument(
            "--encoded-password-stdin",
            action="store_true",
            help=(
                "Read one Django-encoded password from stdin and store it unchanged. "
                "No plaintext strength validation is possible; operator responsibility."
            ),
        )

    def handle(self, *args: Any, **options: Any) -> None:
        if has_active_owner():
            raise CommandError(
                "Server setup is already complete; sign in with an existing Owner."
            )

        password, encoded_password = self._read_password(options)
        try:
            owner = create_first_owner(
                username=options["username"],
                first_name=options["first_name"],
                last_name=options["last_name"],
                email=options["email"],
                server_name=options["server_name"],
                server_description=options["server_description"],
                public_group_name=options["public_group_name"],
                public_group_description=options["public_group_description"],
                advanced_library_groups_enabled=options[
                    "advanced_library_groups_enabled"
                ],
                password=password,
                encoded_password=encoded_password,
            )
        except SetupAlreadyComplete as exc:
            raise CommandError(
                "Server setup is already complete; sign in with an existing Owner."
            ) from exc
        except ValidationError as exc:
            raise CommandError(_validation_error_message(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(f"Server setup complete. Owner: {owner.get_username()}")
        )

    def _read_password(self, options: dict[str, Any]) -> tuple[str | None, str | None]:
        if options["password_stdin"]:
            return _read_one_stdin_value(sys.stdin, label="Password"), None
        if options["encoded_password_stdin"]:
            return None, _read_one_stdin_value(
                sys.stdin,
                label="Encoded password",
            )

        password = getpass.getpass("Password: ")
        confirmation = getpass.getpass("Confirm password: ")
        if not password:
            raise CommandError("Password cannot be empty.")
        if password != confirmation:
            raise CommandError("Passwords do not match.")
        return password, None


def _read_one_stdin_value(stream: TextIO, *, label: str) -> str:
    value = stream.read()
    if value.endswith("\r\n"):
        value = value[:-2]
    elif value.endswith("\n"):
        value = value[:-1]
    if "\r" in value or "\n" in value:
        raise CommandError(f"{label} stdin must contain exactly one value.")
    if not value:
        raise CommandError(f"{label} stdin cannot be empty.")
    return value


def _validation_error_message(exc: ValidationError) -> str:
    if hasattr(exc, "message_dict"):
        messages = [
            f"{field}: {message}"
            for field, field_messages in exc.message_dict.items()
            for message in field_messages
        ]
    else:
        messages = list(exc.messages)
    return "Setup failed: " + "; ".join(messages)
