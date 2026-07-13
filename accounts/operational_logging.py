from __future__ import annotations

import logging

from django.core.exceptions import ObjectDoesNotExist


logger = logging.getLogger(__name__)


def user_uuid(user) -> str:
    if user is None or getattr(user, "is_anonymous", False):
        return "none"
    try:
        return str(user.profile.pk)
    except (AttributeError, ObjectDoesNotExist):
        return "none"
