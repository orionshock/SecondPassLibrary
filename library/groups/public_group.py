from __future__ import annotations

from core.server_settings import get_server_setting, set_server_setting


PUBLIC_GROUP_ID_SETTING = "public_group_id"
DEFAULT_PUBLIC_GROUP_NAME = "Common Room"
DEFAULT_PUBLIC_GROUP_DESCRIPTION = "Main Public Library Room for everyone"


def get_public_group_id() -> str | None:
    value = get_server_setting(PUBLIC_GROUP_ID_SETTING, default=None)
    if value is None:
        return None
    return str(value)


def is_public_group_id(group_id) -> bool:
    public_id = get_public_group_id()
    return bool(public_id and str(group_id) == public_id)


def is_public_group(group) -> bool:
    return is_public_group_id(getattr(group, "id", None))


def get_public_group():
    from library.models import LibraryGroup

    public_id = get_public_group_id()
    if public_id:
        try:
            return LibraryGroup.objects.get(pk=public_id)
        except LibraryGroup.DoesNotExist:
            pass

    group = LibraryGroup.objects.create(
        name=DEFAULT_PUBLIC_GROUP_NAME,
        description=DEFAULT_PUBLIC_GROUP_DESCRIPTION,
    )
    set_server_setting(
        key=PUBLIC_GROUP_ID_SETTING,
        value=str(group.id),
        description="LibraryReWrite2607 Public/Common Room group id.",
    )
    return group
