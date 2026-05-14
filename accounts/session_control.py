from __future__ import annotations

from django.contrib.sessions.models import Session

from .models import UserWebSession


def revoke_web_session(session_key: str) -> None:
    """
    Revoke a single Django web session by session key.

    Best-effort: missing/stale rows are ignored.
    """
    if not session_key:
        return

    Session.objects.filter(session_key=session_key).delete()
    UserWebSession.objects.filter(session_key=session_key).delete()


def revoke_all_web_sessions(user) -> None:
    """
    Revoke all tracked Django web sessions for the given user.
    """
    if not user or getattr(user, "is_anonymous", False):
        return

    keys = list(
        UserWebSession.objects.filter(user=user).values_list("session_key", flat=True)
    )
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
    UserWebSession.objects.filter(user=user).delete()


def revoke_other_web_sessions(user, current_session_key: str | None) -> None:
    """
    Revoke all tracked Django web sessions for the given user except the current session.

    If `current_session_key` is missing/empty, this revokes all sessions.
    """
    if not current_session_key:
        revoke_all_web_sessions(user)
        return

    qs = UserWebSession.objects.filter(user=user).exclude(session_key=current_session_key)
    keys = list(qs.values_list("session_key", flat=True))
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
    qs.delete()


def revoke_all_api_sessions(user) -> None:
    """
    Placeholder for future API/client sessions. No-op for Phase 1.
    """
    return


def user_changed_own_password(user, current_session_key: str | None) -> None:
    revoke_other_web_sessions(user, current_session_key)
    revoke_all_api_sessions(user)


def admin_reset_user_password(user) -> None:
    revoke_all_web_sessions(user)
    revoke_all_api_sessions(user)


def disable_user(user) -> None:
    revoke_all_web_sessions(user)
    revoke_all_api_sessions(user)

