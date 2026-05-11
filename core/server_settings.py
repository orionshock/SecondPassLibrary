from __future__ import annotations

from typing import Any

from django.core.cache import cache
from django.db import transaction

from .models import ServerSetting


SERVER_SETTINGS_CACHE_KEY = "core:server_settings:v1"


def clear_server_settings_cache() -> None:
    cache.delete(SERVER_SETTINGS_CACHE_KEY)


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
        obj, _created = ServerSetting.objects.get_or_create(key=key, defaults={"value": value})
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
    return obj

