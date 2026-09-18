from __future__ import annotations

from typing import Any

from django.conf import settings

from core import server_settings
from core.server_installation import get_installation_id
from library.groups.public_group import get_public_group
from marginalia.profile import MARGINALIA_PROFILE_URI


def server_info_payload() -> dict[str, Any]:
    public_group = get_public_group()
    return {
        "installation_id": get_installation_id(),
        "server_name": server_settings.get_server_name(),
        "server_description": server_settings.get_server_description(),
        "server_banner_message": server_settings.get_server_banner_message(),
        "advanced_library_groups_enabled": (
            server_settings.get_advanced_library_groups_enabled()
        ),
        "second_pass_reader_web_client_url": (
            server_settings.get_second_pass_reader_web_client_url() or None
        ),
        "marginalia_profile_uri": MARGINALIA_PROFILE_URI,
        "public_group": {
            "id": public_group.id,
            "name": public_group.name,
            "description": public_group.description,
        },
        "server_version": settings.SECOND_PASS_SERVER_VERSION,
        "server_release_date": settings.SECOND_PASS_SERVER_RELEASE_DATE,
    }
