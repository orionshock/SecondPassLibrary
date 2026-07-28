from __future__ import annotations

from typing import Any

from django.conf import settings

from core import server_settings
from library.groups.public_group import get_public_group


def server_info_payload() -> dict[str, Any]:
    public_group = get_public_group()
    return {
        "server_name": server_settings.get_server_name(),
        "server_description": server_settings.get_server_description(),
        "server_banner_message": server_settings.get_server_banner_message(),
        "advanced_library_groups_enabled": (
            server_settings.get_advanced_library_groups_enabled()
        ),
        "reading_client_base_url": (
            server_settings.get_reading_client_base_url() or None
        ),
        "public_group": {
            "id": public_group.id,
            "name": public_group.name,
            "description": public_group.description,
        },
        "server_version": settings.SECOND_PASS_SERVER_VERSION,
        "server_release_date": settings.SECOND_PASS_SERVER_RELEASE_DATE,
    }
