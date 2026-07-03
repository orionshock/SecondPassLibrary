from __future__ import annotations

from library import policies as library_policies

from .models import ReadingSession


def _owner_id_from_obj(obj):
    if hasattr(obj, "user_id"):
        return getattr(obj, "user_id")
    if hasattr(obj, "user"):
        return getattr(getattr(obj, "user"), "id", None)
    if hasattr(obj, "session") and hasattr(obj.session, "user_id"):
        return getattr(obj.session, "user_id")
    return None


def can_view_reading_metadata(*, user, obj) -> bool:
    if getattr(user, "is_anonymous", False):
        return False
    owner_id = _owner_id_from_obj(obj)
    return owner_id == getattr(user, "id", None)


def can_edit_reading_metadata(*, user, obj) -> bool:
    return can_view_reading_metadata(user=user, obj=obj)


def can_access_session_book(*, user, session: ReadingSession) -> bool:
    return library_policies.can_view_book(user=user, book=session.book)
