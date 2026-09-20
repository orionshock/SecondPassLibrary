from __future__ import annotations

import uuid

from core.models import ServerIdentity


def get_server_id() -> uuid.UUID:
    """Return the identity created with the database schema."""

    return ServerIdentity.objects.values_list("server_id", flat=True).get(
        pk=ServerIdentity.SINGLETON_ID
    )
