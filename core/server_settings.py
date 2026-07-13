from __future__ import annotations

import logging
from typing import Any

from django.core.cache import cache
from django.db import DatabaseError, transaction

from .models import ServerSetting


SERVER_SETTINGS_CACHE_KEY = "core:server_settings:v1"
APPLICATION_LOG_LEVEL_CACHE_KEY = "core:application_log_level:v1"
SERVER_NAME_SETTING = "server_name"
SERVER_DESCRIPTION_SETTING = "server_description"
SERVER_BANNER_MESSAGE_SETTING = "server_banner_message"
SERVER_NAME_MAX_LEN = 120
SERVER_DESCRIPTION_MAX_LEN = 1000
SERVER_BANNER_MESSAGE_MAX_LEN = 500
DEFAULT_SERVER_NAME = "Second Pass Library"
ADVANCED_LIBRARY_GROUPS_SETTING = "advanced_library_groups_enabled"
APPLICATION_LOG_LEVEL_SETTING = "application_log_level"
APPLICATION_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")
DEFAULT_APPLICATION_LOG_LEVEL = "INFO"
APPLICATION_LOGGER_NAMES = (
    "accounts",
    "core",
    "library",
    "reading",
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
    with transaction.atomic():
        obj, _created = ServerSetting.objects.get_or_create(
            key=key, defaults={"value": value}
        )
        updates: dict[str, Any] = {}
        if obj.value != value:
            updates["value"] = value
        if description and obj.description != description:
            updates["description"] = description
        if updates:
            for k, v in updates.items():
                setattr(obj, k, v)
            obj.save(update_fields=[*updates.keys(), "updated_at"])
    clear_server_settings_cache()
    if key == APPLICATION_LOG_LEVEL_SETTING:
        apply_application_log_level(value)
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


def get_advanced_library_groups_enabled() -> bool:
    value = get_server_setting(ADVANCED_LIBRARY_GROUPS_SETTING, default=False)
    return value is True


def advanced_library_groups_enabled() -> bool:
    return get_advanced_library_groups_enabled()


def enable_advanced_library_groups() -> None:
    set_advanced_library_groups_enabled(True)


def set_advanced_library_groups_enabled(value: bool) -> None:
    set_server_setting(
        key=ADVANCED_LIBRARY_GROUPS_SETTING,
        value=bool(value),
        description=(
            "Whether advanced multi-group management should be presented as a "
            "first-class Product UI feature."
        ),
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
