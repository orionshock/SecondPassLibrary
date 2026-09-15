from __future__ import annotations

import logging
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import URLValidator
from django.core.cache import cache
from django.db import DatabaseError, transaction

from core.operational_logging import info_on_commit, state_change_logging_suppressed
from core.rich_text import sanitize_limited_html

from .models import ServerSetting


logger = logging.getLogger(__name__)
SERVER_SETTINGS_CACHE_KEY = "core:server_settings:v1"
APPLICATION_LOG_LEVEL_CACHE_KEY = "core:application_log_level:v1"
SERVER_SETTINGS_CACHE_SECONDS = 60
APPLICATION_LOG_LEVEL_CACHE_SECONDS = 30
SERVER_NAME_SETTING = "server_name"
SERVER_DESCRIPTION_SETTING = "server_description"
SERVER_BANNER_MESSAGE_SETTING = "server_banner_message"
SECOND_PASS_READER_WEB_CLIENT_URL_SETTING = "second_pass_reader_web_client_url"
SERVER_NAME_MAX_LEN = 120
SERVER_DESCRIPTION_MAX_LEN = 1000
SERVER_BANNER_MESSAGE_MAX_LEN = 500
SECOND_PASS_READER_WEB_CLIENT_URL_MAX_LEN = 2048
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
_UNCHANGED_LOG_LEVEL = object()
_DELETED_SETTING = object()


@dataclass
class _CommittedServerSettingEffects:
    changed: bool = False
    application_log_level: Any = _UNCHANGED_LOG_LEVEL

    def record(self, application_log_level: Any) -> None:
        self.changed = True
        if application_log_level is not _UNCHANGED_LOG_LEVEL:
            self.application_log_level = application_log_level

    def publish(self) -> None:
        if self.changed:
            _publish_server_setting_effects(self.application_log_level)


_SERVER_SETTING_EFFECT_BATCH: ContextVar[_CommittedServerSettingEffects | None] = (
    ContextVar("server_setting_effect_batch", default=None)
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
    SECOND_PASS_READER_WEB_CLIENT_URL_SETTING: {
        "value": "",
        "description": "Canonical base URL of the Second Pass Reader web client.",
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


@contextmanager
def batch_server_setting_writes():
    existing = _SERVER_SETTING_EFFECT_BATCH.get()
    if existing is not None:
        yield
        return

    effects = _CommittedServerSettingEffects()
    token = _SERVER_SETTING_EFFECT_BATCH.set(effects)
    try:
        yield
    finally:
        _SERVER_SETTING_EFFECT_BATCH.reset(token)
        transaction.on_commit(effects.publish)


def schedule_server_setting_effects(*, key: str, value: Any = _DELETED_SETTING) -> None:
    application_log_level: Any = _UNCHANGED_LOG_LEVEL
    if key == APPLICATION_LOG_LEVEL_SETTING:
        application_log_level = (
            DEFAULT_APPLICATION_LOG_LEVEL if value is _DELETED_SETTING else value
        )

    effects = _SERVER_SETTING_EFFECT_BATCH.get()
    if effects is not None:
        transaction.on_commit(lambda: effects.record(application_log_level))
        return
    transaction.on_commit(
        lambda: _publish_server_setting_effects(application_log_level)
    )


def _publish_server_setting_effects(application_log_level: Any) -> None:
    clear_server_settings_cache()
    if application_log_level is not _UNCHANGED_LOG_LEVEL:
        apply_application_log_level(application_log_level)


def get_server_settings_map() -> dict[str, Any]:
    if transaction.get_connection().in_atomic_block:
        return _read_server_settings_map()

    cached = cache.get(SERVER_SETTINGS_CACHE_KEY)
    if isinstance(cached, dict):
        return cached

    settings_map = _read_server_settings_map()
    cache.set(
        SERVER_SETTINGS_CACHE_KEY,
        settings_map,
        timeout=SERVER_SETTINGS_CACHE_SECONDS,
    )
    return settings_map


def _read_server_settings_map() -> dict[str, Any]:
    settings_map: dict[str, Any] = {}
    for row in ServerSetting.objects.all().only("key", "value"):
        settings_map[row.key] = row.value
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
    with transaction.atomic(), batch_server_setting_writes():
        for key, defaults in EDITABLE_SERVER_SETTING_DEFAULTS.items():
            ServerSetting.objects.get_or_create(
                key=key,
                defaults={
                    "value": defaults["value"],
                    "description": defaults["description"],
                },
            )


def _normalize_str(value: Any) -> str:
    return str(value or "").strip()


def get_marginalia_closed_session_tombstone_retention_days() -> int:
    return _fresh_nonnegative_integer_setting(
        MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        DEFAULT_MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS,
    )


def get_marginalia_active_session_tombstone_retention_days() -> int:
    return _fresh_nonnegative_integer_setting(
        MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        DEFAULT_MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS,
    )


def set_marginalia_closed_session_tombstone_retention_days(value: int) -> None:
    _set_nonnegative_integer_setting(
        MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        value,
    )


def set_marginalia_active_session_tombstone_retention_days(value: int) -> None:
    _set_nonnegative_integer_setting(
        MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        value,
    )


def set_marginalia_tombstone_retention_days(
    *, active_days: int, closed_days: int
) -> None:
    _nonnegative_integer_value(
        MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        active_days,
    )
    _nonnegative_integer_value(
        MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        closed_days,
    )
    with transaction.atomic(), batch_server_setting_writes():
        set_marginalia_active_session_tombstone_retention_days(active_days)
        set_marginalia_closed_session_tombstone_retention_days(closed_days)


def get_marginalia_tombstone_retention_days() -> tuple[int, int]:
    keys = {
        MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
        MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
    }
    values = dict(
        ServerSetting.objects.filter(key__in=keys).values_list("key", "value")
    )
    return (
        _nonnegative_integer_value(
            MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            values.get(
                MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
                DEFAULT_MARGINALIA_ACTIVE_SESSION_TOMBSTONE_RETENTION_DAYS,
            ),
        ),
        _nonnegative_integer_value(
            MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
            values.get(
                MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS_SETTING,
                DEFAULT_MARGINALIA_CLOSED_SESSION_TOMBSTONE_RETENTION_DAYS,
            ),
        ),
    )


def _fresh_nonnegative_integer_setting(key: str, default: int) -> int:
    row = ServerSetting.objects.filter(key=key).values_list("key", "value").first()
    return _nonnegative_integer_value(key, default if row is None else row[1])


def _nonnegative_integer_value(key: str, value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer.")
    return value


def _set_nonnegative_integer_setting(key: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{key} must be a non-negative integer.")
    set_server_setting(
        key=key,
        value=value,
        description=EDITABLE_SERVER_SETTING_DEFAULTS[key]["description"],
    )


def get_server_name() -> str:
    value = get_server_setting(SERVER_NAME_SETTING, default=None)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return DEFAULT_SERVER_NAME


def normalize_server_name(value: str) -> str:
    normalized = _normalize_str(value)
    if not normalized:
        raise ValueError("Server name is required.")
    if len(normalized) > SERVER_NAME_MAX_LEN:
        raise ValueError(
            f"Server name must be at most {SERVER_NAME_MAX_LEN} characters."
        )
    return normalized


def set_server_name(value: str) -> None:
    normalized = normalize_server_name(value)
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
    normalized = normalize_server_description(value)
    set_server_setting(
        key=SERVER_DESCRIPTION_SETTING,
        value=normalized,
        description="Optional server description used in discovery.",
    )


def normalize_server_description(value: str) -> str:
    normalized = sanitize_limited_html(value).strip()
    if len(normalized) > SERVER_DESCRIPTION_MAX_LEN:
        raise ValueError(
            f"Server description must be at most {SERVER_DESCRIPTION_MAX_LEN} characters."
        )
    return normalized


def get_server_banner_message() -> str:
    value = get_server_setting(SERVER_BANNER_MESSAGE_SETTING, default=None)
    if isinstance(value, str):
        normalized = value.strip()
        if normalized:
            return normalized
    return ""


def set_server_banner_message(value: str) -> None:
    normalized = normalize_server_banner_message(value)
    set_server_setting(
        key=SERVER_BANNER_MESSAGE_SETTING,
        value=normalized,
        description="Optional banner message shown at the top of the dashboard.",
    )


def normalize_server_banner_message(value: str) -> str:
    normalized = sanitize_limited_html(value).strip()
    if len(normalized) > SERVER_BANNER_MESSAGE_MAX_LEN:
        raise ValueError(
            f"Server banner message must be at most {SERVER_BANNER_MESSAGE_MAX_LEN} characters."
        )
    return normalized


def set_server_identity(*, name: str, description: str, banner_message: str) -> None:
    values: dict[str, str] = {}
    errors: dict[str, list[str]] = {}
    normalizers = {
        SERVER_NAME_SETTING: (normalize_server_name, name),
        SERVER_DESCRIPTION_SETTING: (normalize_server_description, description),
        SERVER_BANNER_MESSAGE_SETTING: (
            normalize_server_banner_message,
            banner_message,
        ),
    }
    for field, (normalize, value) in normalizers.items():
        try:
            values[field] = normalize(value)
        except ValueError as exc:
            errors[field] = [str(exc)]
    if errors:
        raise ValidationError(errors)

    with transaction.atomic(), batch_server_setting_writes():
        set_server_name(values[SERVER_NAME_SETTING])
        set_server_description(values[SERVER_DESCRIPTION_SETTING])
        set_server_banner_message(values[SERVER_BANNER_MESSAGE_SETTING])


def normalize_second_pass_reader_web_client_url(value: Any) -> str:
    normalized = _normalize_str(value)
    if not normalized:
        return ""
    if len(normalized) > SECOND_PASS_READER_WEB_CLIENT_URL_MAX_LEN:
        raise ValueError(
            "Second Pass Reader Web Client URL must be at most "
            f"{SECOND_PASS_READER_WEB_CLIENT_URL_MAX_LEN} characters."
        )
    if "{" in normalized or "}" in normalized:
        raise ValueError(
            "Second Pass Reader Web Client URL cannot contain placeholders."
        )

    try:
        parsed = urlsplit(normalized)
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Second Pass Reader Web Client URL is invalid.") from exc
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("Second Pass Reader Web Client URL must use http or https.")
    if not parsed.hostname:
        raise ValueError("Second Pass Reader Web Client URL must include a hostname.")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(
            "Second Pass Reader Web Client URL cannot include user information."
        )
    if port is not None and not 0 < port <= 65535:
        raise ValueError("Second Pass Reader Web Client URL has an invalid port.")
    try:
        URLValidator(schemes=["http", "https"])(normalized)
    except ValidationError as exc:
        raise ValueError("Second Pass Reader Web Client URL is invalid.") from exc

    hostname = parsed.hostname
    if ":" in hostname:
        hostname = f"[{hostname}]"
    netloc = hostname if port is None else f"{hostname}:{port}"
    return f"{parsed.scheme}://{netloc}"


def second_pass_reader_web_client_url_locked() -> bool:
    return bool(str(settings.SECOND_PASS_READER_WEB_CLIENT_URL or "").strip())


def get_second_pass_reader_web_client_url() -> str:
    return normalize_second_pass_reader_web_client_url(
        get_server_setting(SECOND_PASS_READER_WEB_CLIENT_URL_SETTING, default="")
    )


def set_second_pass_reader_web_client_url(value: str) -> None:
    if second_pass_reader_web_client_url_locked():
        raise ValueError(
            "Second Pass Reader Web Client URL is configured by the server environment."
        )
    _store_second_pass_reader_web_client_url(value)


def synchronize_deployment_server_settings() -> bool:
    configured = str(settings.SECOND_PASS_READER_WEB_CLIENT_URL or "").strip()
    if not configured:
        return False
    _store_second_pass_reader_web_client_url(configured)
    return True


def _store_second_pass_reader_web_client_url(value: str) -> None:
    normalized = normalize_second_pass_reader_web_client_url(value)
    set_server_setting(
        key=SECOND_PASS_READER_WEB_CLIENT_URL_SETTING,
        value=normalized,
        description="Canonical base URL of the Second Pass Reader web client.",
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
        value = (
            ServerSetting.objects.filter(key=APPLICATION_LOG_LEVEL_SETTING)
            .values_list("value", flat=True)
            .first()
        )
    except DatabaseError:
        return apply_application_log_level(DEFAULT_APPLICATION_LOG_LEVEL)
    if value is None:
        value = DEFAULT_APPLICATION_LOG_LEVEL
    level_name = _normalized_application_log_level(value)
    cache.set(
        APPLICATION_LOG_LEVEL_CACHE_KEY,
        level_name,
        timeout=APPLICATION_LOG_LEVEL_CACHE_SECONDS,
    )
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
        SECOND_PASS_READER_WEB_CLIENT_URL_SETTING,
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
