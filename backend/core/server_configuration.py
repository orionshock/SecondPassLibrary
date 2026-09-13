from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from django.core.exceptions import ValidationError
from django.db import transaction

from core import server_settings
from core.operational_logging import (
    info_on_commit,
    suppress_state_change_logging,
    user_uuid,
)
from library.groups.public_group import get_public_group
from library.groups.public_services import (
    configure_public_group,
    normalize_public_group_configuration,
)


logger = logging.getLogger(__name__)
ALLOWED_PATCH_FIELDS = frozenset(
    {
        "server_name",
        "server_description",
        "server_banner_message",
        "second_pass_reader_web_client_url",
        "public_group_name",
        "public_group_description",
    }
)
IDENTITY_FIELDS = (
    "server_name",
    "server_description",
    "server_banner_message",
)


class ServerConfigurationPatchError(ValueError):
    def __init__(
        self,
        *,
        errors: dict[str, list[str]] | None = None,
        unknown_fields: tuple[str, ...] = (),
    ) -> None:
        super().__init__()
        self.errors = errors or {}
        self.unknown_fields = unknown_fields


@dataclass(frozen=True, slots=True)
class _ValidatedPatch:
    values: dict[str, Any]
    identity_requested: bool
    reader_url_requested: bool
    public_group_requested: bool


def get_owner_server_configuration() -> dict[str, Any]:
    public_group = get_public_group()
    return {
        "server_name": server_settings.get_server_name(),
        "server_description": server_settings.get_server_description(),
        "server_banner_message": server_settings.get_server_banner_message(),
        "public_group_name": public_group.name,
        "public_group_description": public_group.description,
        "advanced_library_groups_enabled": (
            server_settings.get_advanced_library_groups_enabled()
        ),
        "second_pass_reader_web_client_url": (
            server_settings.get_second_pass_reader_web_client_url()
        ),
        "second_pass_reader_web_client_url_locked": (
            server_settings.second_pass_reader_web_client_url_locked()
        ),
    }


def update_owner_server_configuration(
    *, patch: Mapping[str, Any], actor=None
) -> dict[str, Any]:
    requested_fields = tuple(sorted(patch))
    try:
        with transaction.atomic():
            validated = _validate_patch(patch)
            if any(
                (
                    validated.identity_requested,
                    validated.reader_url_requested,
                    validated.public_group_requested,
                )
            ):
                with (
                    server_settings.batch_server_setting_writes(),
                    suppress_state_change_logging(),
                ):
                    if validated.identity_requested:
                        server_settings.set_server_identity(
                            name=validated.values["server_name"],
                            description=validated.values["server_description"],
                            banner_message=validated.values["server_banner_message"],
                        )
                    if validated.reader_url_requested:
                        server_settings.set_second_pass_reader_web_client_url(
                            validated.values["second_pass_reader_web_client_url"]
                        )
                    if validated.public_group_requested:
                        configure_public_group(
                            name=validated.values["public_group_name"],
                            description=validated.values["public_group_description"],
                        )
                info_on_commit(
                    logger,
                    "Owner server configuration updated: actor=%s fields=%s "
                    "transaction=committed",
                    user_uuid(actor),
                    ",".join(requested_fields),
                )
    except ServerConfigurationPatchError:
        raise
    except Exception as exc:
        logger.error(
            "Owner server configuration update failed: actor=%s fields=%s "
            "failure_class=%s transaction=rolled_back retry_suitable=true",
            user_uuid(actor),
            ",".join(requested_fields) or "none",
            type(exc).__name__,
        )
        raise
    return validated.values


def _validate_patch(patch: Mapping[str, Any]) -> _ValidatedPatch:
    unknown_fields = tuple(sorted(set(patch) - ALLOWED_PATCH_FIELDS))
    if unknown_fields:
        raise ServerConfigurationPatchError(unknown_fields=unknown_fields)

    values = get_owner_server_configuration()
    errors: dict[str, list[str]] = {}
    normalizers = {
        "server_name": server_settings.normalize_server_name,
        "server_description": server_settings.normalize_server_description,
        "server_banner_message": server_settings.normalize_server_banner_message,
    }
    for field in IDENTITY_FIELDS:
        if field not in patch:
            continue
        try:
            values[field] = normalizers[field](str(patch.get(field) or ""))
        except ValueError as exc:
            errors[field] = [str(exc)]

    reader_url_requested = "second_pass_reader_web_client_url" in patch
    if reader_url_requested:
        try:
            if server_settings.second_pass_reader_web_client_url_locked():
                raise ValueError(
                    "Second Pass Reader Web Client URL is configured by the "
                    "server environment."
                )
            values["second_pass_reader_web_client_url"] = (
                server_settings.normalize_second_pass_reader_web_client_url(
                    patch.get("second_pass_reader_web_client_url")
                )
            )
        except ValueError as exc:
            errors["second_pass_reader_web_client_url"] = [str(exc)]

    public_group_requested = any(
        field in patch and patch[field] is not None
        for field in ("public_group_name", "public_group_description")
    )
    if public_group_requested:
        try:
            name, description = normalize_public_group_configuration(
                name=(
                    str(patch["public_group_name"])
                    if patch.get("public_group_name") is not None
                    else values["public_group_name"]
                ),
                description=(
                    str(patch.get("public_group_description") or "")
                    if patch.get("public_group_description") is not None
                    else values["public_group_description"]
                ),
            )
            values["public_group_name"] = name
            values["public_group_description"] = description
        except ValidationError as exc:
            for field, messages in exc.message_dict.items():
                wire_field = (
                    "public_group_description" if field == "description" else field
                )
                errors[wire_field] = list(messages)

    if errors:
        raise ServerConfigurationPatchError(errors=errors)
    return _ValidatedPatch(
        values=values,
        identity_requested=any(field in patch for field in IDENTITY_FIELDS),
        reader_url_requested=reader_url_requested,
        public_group_requested=public_group_requested,
    )
