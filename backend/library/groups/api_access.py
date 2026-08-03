from __future__ import annotations

from django.http import Http404

from core.server_settings import advanced_library_groups_enabled
from library.groups.public_group import get_public_group_id


def groups_available_via_api(queryset):
    if advanced_library_groups_enabled():
        return queryset

    public_group_id = get_public_group_id()
    if public_group_id is None:
        return queryset.none()
    return queryset.filter(pk=public_group_id)


def require_group_creation_available() -> None:
    if not advanced_library_groups_enabled():
        raise Http404
