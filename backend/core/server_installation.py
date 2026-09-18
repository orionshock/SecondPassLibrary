from __future__ import annotations

import uuid

from core.models import ServerInstallation


def get_installation_id() -> uuid.UUID:
    """Return the identity created with the database schema."""

    return ServerInstallation.objects.values_list(
        "installation_id", flat=True
    ).get(pk=ServerInstallation.SINGLETON_ID)
