from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.core.cache import cache
from django.db import DatabaseError, transaction

from core.operational_logging import info_on_commit, state_change_logging_suppressed

from .models import ServerSetting


logger = logging.getLogger(__name__)
SERVER_SETTINGS_CACHE_KEY = "core:server_settings:v1"
APPLICATION_LOG_LEVEL_CACHE_KEY = "core:application_log_level:v1"
SERVER_NAME_SETTING = "server_name"
SERVER_DESCRIPTION_SETTING = "server_description"
SERVER_BANNER_MESSAGE_SETTING = "server_banner_message"
READING_CLIENT_BASE_URL_SETTING = "reading_client_base_url"
SERVER_NAME_MAX_LEN = 120
SERVER_DESCRIPTION_MAX_LEN = 1000
SERVER_BANNER_MESSAGE_MAX_LEN = 500
READING_CLIENT_BASE_URL_MAX_LEN = 2048
DEFAULT_SERVER_NAME = "Second Pass Library"
ADVANCED_LIBRARY_GROUPS_SETTING = "advanced_library_groups_enabled"
APPLICATION_LOG_LEVEL_SETTING = "application_log_level"
MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING = (
    "marginalia_closed_session_tombstone_retention_days"
)
MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING = (
    "marginalia_active_session_tombstone_retention_days"
)
DEFAULT_MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS = 7
DEFAULT_MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS = 28
APPLICATION_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_APPLICATION_LOG_LEVEL = "INFO"
APPLICATION_LOGGER_NAMES = (
    "accounts",
    "core",
    "library",
    "maintenance",
    "marginalia",
    "shelves",
    "web",
)

EDITABLE_SERVER_SETTING_DEFAULTS = {
    SERVER_NAME_SETTING: {
        "value": DEFAULT_SERVER_NAME,
        "description": "Server display name used in UI and discovery.",
    },
    SERVER_DESCRIPTION_SETTING: {
        "value": "",
        "description": "Optional server description used in discovery.",
    },
    SERVER_BANNER_MESSAGE_SETTING: {
        "value": "",
        "description": "Optional banner message shown at the top of the dashboard.",
    },
    READING_CLIENT_BASE_URL_SETTING: {
        "value": "",
        "description": "Optional root URL of the external Reading Client.",
    },
    ADVANCED_LIBRARY_GROUPS_SETTING: {
        "value": False,
        "description": (
            "Whether advanced multi-group management should be presented as a "
            "first-class Product UI feature."
        ),
    },
    APPLICATION_LOG_LEVEL_SETTING: {
        "value": DEFAULT_APPLICATION_LOG_LEVEL,
        "description": (
            "Controls diagnostic output from Second Pass Library application code."
        ),
    },
    MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING: {
        "value": DEFAULT_MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS,
        "description": (
            "Days to retain soft-deleted Annotations from closed Reading Sessions."
        ),
    },
    MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING: {
        "value": DEFAULT_MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS,
        "description": (
            "Days to retain soft-deleted Annotations from active Reading Sessions."
        ),
    },
}


def clear_server_settings_cache() -> None:
    cache.delete(SERVER_SETTINGS_CACHE_KEY)
    cache.delete(APPLICATION_LOG_LEVEL_CACHE_KEY)


def get_server_settings_map() -> dict[str, Any]:
    cached = cache.get(SERVER_SETTINGS_CACHE_KEY)
    if isinstance(cached, dict):
        return cached

    settings_map: dict[str, Any] = {}
    for row in ServerSetting.objects.all().only("key", "value"):
        settings_map[row.key] = row.value

    # Cache indefinitely; invalidated explicitly on writes.
    cache.set(SERVER_SETTINGS_CACHE_KEY, settings_map, timeout=None)
    return settings_map


def get_server_setting(key: str, default: Any | None = None) -> Any:
    settings_map = get_server_settings_map()
    return settings_map.get(key, default)


def set_server_setting(*, key: str, value: Any, description: str = "") -> ServerSetting:
    old_value: Any | None = None
    was_created = False
    changed_fields: list[str] = []
    with transaction.atomic():
        obj, was_created = ServerSetting.objects.get_or_create(
            key=key,
            defaults={"value": value, "description": description or ""},
        )
        if not was_created:
            old_value = obj.value
        updates: dict[str, Any] = {}
        if obj.value != value:
            updates["value"] = value
        if description and obj.description != description:
            updates["description"] = description
        if updates:
            for k, v in updates.items():
                setattr(obj, k, v)
            obj.save(update_fields=[*updates.keys(), "updated_at"])
        changed_fields = sorted(updates.keys())
    clear_server_settings_cache()
    if key == APPLICATION_LOG_LEVEL_SETTING:
        apply_application_log_level(value)
    if (was_created or changed_fields) and not state_change_logging_suppressed():
        scheduled_fields = list(changed_fields or ["value"])
        transaction.on_commit(
            lambda: _log_server_setting_changed(
                key=key,
                old_value=old_value,
                new_value=value,
                changed_fields=scheduled_fields,
                created=was_created,
            )
        )
    return obj


def ensure_editable_server_settings() -> None:
    created = False
    with transaction.atomic():
        for key, defaults in EDITABLE_SERVER_SETTING_DEFAULTS.items():
            _obj, was_created = ServerSetting.objects.get_or_create(
                key=key,
                defaults={
                    "value": defaults["value"],
                    "description": defaults["description"],
                },
            )
            created = created or was_created
    if created:
        clear_server_settings_cache()


def _normalize_str(value: Any) -> str:
    return str(value or "").strip()


def get_marginalia_closed_session_tombstone_retention_days() -> int:
    return _nonnegative_integer_setting(
        MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        DEFAULT_MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS,
    )


def get_marginalia_active_session_tombstone_retention_days() -> int:
    return _nonnegative_integer_setting(
        MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        DEFAULT_MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS,
    )


def _nonnegative_integer_setting(key: str, default: int) -> int:
    value = get_server_setting(key, default=default)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer.")
    return value


def get_server_name() -> str:
    value = get_server_setting(SERVER_NAME_SETTING, default=None)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return DEFAULT_SERVER_NAME


def set_server_name(value: str) -> None:
    normalized = _normalize_str(value)
    if not normalized:
        raise ValueError("Server name is required.")
    if len(normalized) > SERVER_NAME_MAX_LEN:
        raise ValueError(
            f"Server name must be at most {SERVER_NAME_MAX_LEN} characters."
        )
    set_server_setting(
        key=SERVER_NAME_SETTING,
        value=normalized,
        description="Server display name used in UI and discovery.",
    )


def get_server_description() -> str:
    value = get_server_setting(SERVER_DESCRIPTION_SETTING, default=None)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return ""


def set_server_description(value: str) -> None:
    normalized = _normalize_str(value)
    if len(normalized) > SERVER_DESCRIPTION_MAX_LEN:
        raise ValueError(
            f"Server description must be at most {SERVER_DESCRIPTION_MAX_LEN} characters."
        )
    set_server_setting(
        key=SERVER_DESCRIPTION_SETTING,
        value=normalized,
        description="Optional server description used in discovery.",
    )


def get_server_banner_message() -> str:
    value = get_server_setting(SERVER_BANNER_MESSAGE_SETTING, default=None)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return ""


def set_server_banner_message(value: str) -> None:
    normalized = _normalize_str(value)
    if len(normalized) > SERVER_BANNER_MESSAGE_MAX_LEN:
        raise ValueError(
            f"Server banner message must be at most {SERVER_BANNER_MESSAGE_MAX_LEN} characters."
        )
    set_server_setting(
        key=SERVER_BANNER_MESSAGE_SETTING,
        value=normalized,
        description="Optional banner message shown at the top of the dashboard.",
    )


def normalize_reading_client_base_url(value: Any) -> str:
    normalized = _normalize_str(value)
    if not normalized:
        return ""
    if len(normalized) > READING_CLIENT_BASE_URL_MAX_LEN:
        raise ValueError(
            "Reading Client URL must be at most "
            f"{READING_CLIENT_BASE_URL_MAX_LEN} characters."
        )
    if "{" in normalized or "}" in normalized:
        raise ValueError("Reading Client URL cannot contain placeholders.")

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Reading Client URL is invalid.") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Reading Client URL must use http or https.")
    if not parsed.hostname:
        raise ValueError("Reading Client URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Reading Client URL cannot include user information.")
    if parsed.path not in {"", "/"}:
        raise ValueError("Reading Client URL must not include a path.")
    if parsed.query or parsed.fragment:
        raise ValueError("Reading Client URL must not include a query or fragment.")
    if port is not None and not 0 < port <= 65535:
        raise ValueError("Reading Client URL has an invalid port.")
    try:
        URLValidator(schemes=["http", "https"])(normalized)
    except ValidationError as exc:
        raise ValueError("Reading Client URL is invalid.") from exc
    return f"{parsed.scheme}://{parsed.netloc}"


def reading_client_base_url_locked() -> bool:
    return bool(str(settings.SECOND_PASS_READING_CLIENT_BASE_URL or "").strip())


def get_reading_client_base_url() -> str:
    if reading_client_base_url_locked():
        return normalize_reading_client_base_url(
            settings.SECOND_PASS_READING_CLIENT_BASE_URL
        )
    return normalize_reading_client_base_url(
        get_server_setting(READING_CLIENT_BASE_URL_SETTING, default="")
    )


def set_reading_client_base_url(value: str) -> None:
    if reading_client_base_url_locked():
        raise ValueError("Reading Client URL is configured by the server environment.")
    normalized = normalize_reading_client_base_url(value)
    set_server_setting(
        key=READING_CLIENT_BASE_URL_SETTING,
        value=normalized,
        description="Optional root URL of the external Reading Client.",
    )


def get_advanced_library_groups_enabled() -> bool:
    value = get_server_setting(ADVANCED_LIBRARY_GROUPS_SETTING, default=False)
    return value is True


def advanced_library_groups_enabled() -> bool:
    return get_advanced_library_groups_enabled()


def enable_advanced_library_groups() -> None:
    set_advanced_library_groups_enabled(True)


def set_advanced_library_groups_enabled(value: bool) -> None:
    old_value = get_advanced_library_groups_enabled()
    set_server_setting(
        key=ADVANCED_LIBRARY_GROUPS_SETTING,
        value=bool(value),
        description=(
            "Whether advanced multi-group management should be presented as a "
            "first-class Product UI feature."
        ),
    )
    if (
        bool(value)
        and not old_value
        and not state_change_logging_suppressed()
    ):
        info_on_commit(
            logger,
            "Advanced library groups enabled: setting_key=%s old=%s new=%s",
            ADVANCED_LIBRARY_GROUPS_SETTING,
            old_value,
            True,
        )


def _normalized_application_log_level(value: Any) -> str:
    if isinstance(value, str):
        normalized = value.strip()
        if normalized in APPLICATION_LOG_LEVELS:
            return normalized
    return DEFAULT_APPLICATION_LOG_LEVEL


def apply_application_log_level(value: Any) -> str:
    level_name = _normalized_application_log_level(value)
    level = getattr(logging, level_name)
    for logger_name in APPLICATION_LOGGER_NAMES:
        logging.getLogger(logger_name).setLevel(level)
    return level_name


def get_application_log_level() -> str:
    cached = cache.get(APPLICATION_LOG_LEVEL_CACHE_KEY)
    if cached in APPLICATION_LOG_LEVELS:
        return apply_application_log_level(cached)
    try:
        value = get_server_setting(
            APPLICATION_LOG_LEVEL_SETTING,
            default=DEFAULT_APPLICATION_LOG_LEVEL,
        )
    except DatabaseError:
        return apply_application_log_level(DEFAULT_APPLICATION_LOG_LEVEL)
    level_name = _normalized_application_log_level(value)
    cache.set(APPLICATION_LOG_LEVEL_CACHE_KEY, level_name, timeout=None)
    return apply_application_log_level(level_name)


def set_application_log_level(value: str) -> None:
    normalized = str(value or "").strip()
    if normalized not in APPLICATION_LOG_LEVELS:
        raise ValueError("Application log level must be DEBUG, INFO, WARNING, or ERROR.")
    set_server_setting(
        key=APPLICATION_LOG_LEVEL_SETTING,
        value=normalized,
        description=(
            "Controls diagnostic output from Second Pass Library application code."
        ),
    )


def _log_server_setting_changed(
    *,
    key: str,
    old_value: Any,
    new_value: Any,
    changed_fields: list[str],
    created: bool,
) -> None:
    if key in {
        SERVER_NAME_SETTING,
        SERVER_DESCRIPTION_SETTING,
        SERVER_BANNER_MESSAGE_SETTING,
        READING_CLIENT_BASE_URL_SETTING,
    }:
        logger.info(
            "Server setting changed: setting_key=%s changed_fields=%s created=%s",
            key,
            ",".join(changed_fields),
            created,
        )
        return
    if key == APPLICATION_LOG_LEVEL_SETTING:
        logger.info(
            "Server setting changed: setting_key=%s changed_fields=%s old=%s new=%s created=%s",
            key,
            ",".join(changed_fields),
            _normalized_application_log_level(old_value),
            _normalized_application_log_level(new_value),
            created,
        )
        return
    if key == ADVANCED_LIBRARY_GROUPS_SETTING:
        logger.info(
            "Server setting changed: setting_key=%s changed_fields=%s old=%s new=%s created=%s",
            key,
            ",".join(changed_fields),
            old_value is True,
            new_value is True,
            created,
        )
        return
    logger.info(
        "Server setting changed: setting_key=%s changed_fields=%s created=%s",
        key,
        ",".join(changed_fields),
        created,
    )
