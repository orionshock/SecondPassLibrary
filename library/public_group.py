from __future__ import annotations

from typing import TYPE_CHECKING
import uuid

from core.server_settings import get_server_setting, set_server_setting

if TYPE_CHECKING:
    from .models import LibraryGroup


PUBLIC_GROUP_ID_SETTING = "public_group_id"
DEFAULT_PUBLIC_GROUP_NAME = "Common Room"
DEFAULT_PUBLIC_GROUP_DESCRIPTION = "Main Public Library Room for everyone"


def _parse_uuid_setting_value(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            return str(uuid.UUID(s))
        except (ValueError, AttributeError, TypeError):
            return None
    return None


def get_public_group_id() -> str | None:
    value = get_server_setting(PUBLIC_GROUP_ID_SETTING, default=None)
    return _parse_uuid_setting_value(value)


def set_public_group_id(group_id: str) -> None:
    set_server_setting(
        key=PUBLIC_GROUP_ID_SETTING,
        value=str(group_id),
        description="UUID of the server-wide Public LibraryGroup (default/fallback access scope).",
    )


def get_public_group() -> LibraryGroup:
    """
    Return the server-wide Public LibraryGroup (default/fallback access scope).

    Public is identified by the ServerSetting `public_group_id` rather than a
    slug or display name. If missing or invalid, this function repairs the
    setting and/or creates the default public group.
    """
    from .models import LibraryGroup

    public_id = get_public_group_id()
    if public_id is not None:
        try:
            group = LibraryGroup.objects.get(pk=public_id)
        except LibraryGroup.DoesNotExist:
            group = None

        if group is not None:
            return group

    group = LibraryGroup.objects.create(
        name=DEFAULT_PUBLIC_GROUP_NAME,
        description=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    )
    set_public_group_id(str(group.id))
    return group


def is_public_group_id(group_id) -> bool:
    if group_id is None:
        return False

    public_id = get_public_group_id()
    if public_id is None:
        get_public_group()
        public_id = get_public_group_id()

    if public_id is None or public_id == "":
        return False
    return str(group_id) == str(public_id)


def is_public_group(group: LibraryGroup | None) -> bool:
    if group is None:
        return False
    return is_public_group_id(getattr(group, "id", None))
