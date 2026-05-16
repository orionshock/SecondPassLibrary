from __future__ import annotations

from . import server_settings


def server_identity(request):
    return {
        "server_name": server_settings.get_server_name(),
        "server_description": server_settings.get_server_description(),
    }

