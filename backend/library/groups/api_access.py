from __future__ import annotations

from django.http import Http404

from core.server_settings import advanced_library_groups_enabled
from library.groups.public_group import is_public_group


def require_group_creation_available() -> None:
    if not advanced_library_groups_enabled():
        raise Http404


def require_group_mutation_available(group) -> None:
    """Reject custom-Group management in Simple Mode without hiding Group reads."""
    if not advanced_library_groups_enabled() and not is_public_group(group):
        raise Http404
