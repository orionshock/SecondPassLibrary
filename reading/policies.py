from __future__ import annotations

from core import policies as core_policies

from .models import ReadingSession


def can_access_session_book(*, user, session: ReadingSession) -> bool:
    return core_policies.can_view_book(user=user, book=session.book)
