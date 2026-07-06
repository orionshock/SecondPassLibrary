from __future__ import annotations

from django.utils.translation import gettext_lazy as _


SERVER_SETTING_DISPLAY_NAMES = {
    "advanced_library_groups_enabled": _("Advanced Library Groups"),
    "public_group_id": _("Public Group"),
    "server_banner_message": _("Server Banner Message"),
    "server_description": _("Server Description"),
    "server_name": _("Server Name"),
}


def server_setting_display_name(key: str):
    return SERVER_SETTING_DISPLAY_NAMES.get(
        key,
        key.replace("_", " ").title(),
    )
