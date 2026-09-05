from __future__ import annotations

from django.utils.translation import gettext_lazy as _


SERVER_SETTING_DISPLAY_NAMES = {
    "advanced_library_groups_enabled": _("Advanced Library Groups"),
    "application_log_level": _("Application Log Level"),
    "marginalia_active_session_tombstone_retention_days": _(
        "Active Session Annotation Tombstone Retention"
    ),
    "marginalia_closed_session_tombstone_retention_days": _(
        "Closed Session Annotation Tombstone Retention"
    ),
    "public_group_id": _("Public/Common Room Group"),
    "reading_client_base_url": _("Reading Client URL"),
    "server_banner_message": _("Server Banner Message"),
    "server_description": _("Server Description"),
    "server_name": _("Server Identity & Banner"),
}


def server_setting_display_name(key: str):
    return SERVER_SETTING_DISPLAY_NAMES.get(
        key,
        key.replace("_", " ").title(),
    )
