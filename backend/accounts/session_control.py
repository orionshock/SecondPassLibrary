from __future__ import annotations

from dataclasses import dataclass

from django.contrib.sessions.models import Session
from django.utils import timezone

from accounts.operational_logging import logger, user_uuid
from core.operational_logging import info_on_commit

from .models import UserClientSession, UserWebSession


@dataclass(frozen=True)
class SessionRevocationCounts:
    web_sessions: int = 0
    client_sessions: int = 0


def revoke_web_session(session_key: str) -> int:
    """
    Revoke a single Django web session by session key.

    Best-effort: missing/stale rows are ignored.
    """
    if not session_key:
        return 0

    Session.objects.filter(session_key=session_key).delete()
    deleted, _ = UserWebSession.objects.filter(session_key=session_key).delete()
    return deleted


def revoke_all_web_sessions(user) -> int:
    """
    Revoke all tracked Django web sessions for the given user.
    """
    if not user or getattr(user, "is_anonymous", False):
        return 0

    keys = list(
        UserWebSession.objects.filter(user=user).values_list("session_key", flat=True)
    )
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
    deleted, _ = UserWebSession.objects.filter(user=user).delete()
    return deleted


def revoke_other_web_sessions(
    user,
    current_session_key: str | None,
    *,
    actor=None,
    reason: str = "manual_revoke",
    log_event: bool = True,
) -> int:
    """
    Revoke all tracked Django web sessions for the given user except the current session.

    If `current_session_key` is missing/empty, this revokes all sessions.
    """
    try:
        if not current_session_key:
            count = revoke_all_web_sessions(user)
        else:
            qs = UserWebSession.objects.filter(user=user).exclude(session_key=current_session_key)
            keys = list(qs.values_list("session_key", flat=True))
            if keys:
                Session.objects.filter(session_key__in=keys).delete()
            count, _ = qs.delete()
    except Exception as exc:
        logger.error(
            "Web session revocation failed: actor=%s target=%s reason=%s exception=%s",
            user_uuid(actor),
            user_uuid(user),
            reason,
            type(exc).__name__,
        )
        raise
    if log_event:
        logger.info(
            "Web sessions revoked: actor=%s target=%s reason=%s count=%d",
            user_uuid(actor),
            user_uuid(user),
            reason,
            count,
        )
    return count


def revoke_all_api_sessions(
    user,
    *,
    actor=None,
    reason: str = "manual_revoke",
    log_event: bool = True,
) -> int:
    """
    Revoke all Client API bearer sessions for the given user.
    """
    if not user or getattr(user, "is_anonymous", False):
        return 0

    now = timezone.now()
    try:
        count = UserClientSession.objects.filter(user=user, revoked_at__isnull=True).update(
            revoked_at=now, updated_at=now
        )
    except Exception as exc:
        logger.error(
            "Client session revocation failed: actor=%s target=%s reason=%s exception=%s",
            user_uuid(actor),
            user_uuid(user),
            reason,
            type(exc).__name__,
        )
        raise
    if log_event:
        logger.info(
            "Client sessions revoked: actor=%s target=%s reason=%s count=%d",
            user_uuid(actor),
            user_uuid(user),
            reason,
            count,
        )
    return count


def user_changed_own_password(user, current_session_key: str | None) -> SessionRevocationCounts:
    web_count = revoke_other_web_sessions(
        user,
        current_session_key,
        actor=user,
        reason="password_change",
        log_event=False,
    )
    client_count = revoke_all_api_sessions(
        user,
        actor=user,
        reason="password_change",
        log_event=False,
    )
    info_on_commit(
        logger,
        "Sessions revoked: actor=%s target=%s reason=password_change "
        "web_sessions=%d client_sessions=%d",
        user_uuid(user),
        user_uuid(user),
        web_count,
        client_count,
    )
    return SessionRevocationCounts(web_sessions=web_count, client_sessions=client_count)


def admin_reset_user_password(user, *, actor=None) -> SessionRevocationCounts:
    web_count = revoke_other_web_sessions(
        user,
        None,
        actor=actor,
        reason="managed_reset",
        log_event=False,
    )
    client_count = revoke_all_api_sessions(
        user,
        actor=actor,
        reason="managed_reset",
        log_event=False,
    )
    info_on_commit(
        logger,
        "Sessions revoked: actor=%s target=%s reason=managed_reset "
        "web_sessions=%d client_sessions=%d",
        user_uuid(actor),
        user_uuid(user),
        web_count,
        client_count,
    )
    return SessionRevocationCounts(web_sessions=web_count, client_sessions=client_count)


def disable_user(user, *, actor=None) -> SessionRevocationCounts:
    web_count = revoke_other_web_sessions(
        user,
        None,
        actor=actor,
        reason="user_disabled",
        log_event=True,
    )
    client_count = revoke_all_api_sessions(
        user,
        actor=actor,
        reason="user_disabled",
        log_event=True,
    )
    return SessionRevocationCounts(web_sessions=web_count, client_sessions=client_count)


def revoke_client_session(session: UserClientSession, *, actor=None) -> int:
    try:
        now = timezone.now()
        count = UserClientSession.objects.filter(
            pk=session.pk,
            revoked_at__isnull=True,
        ).update(revoked_at=now, updated_at=now)
    except Exception as exc:
        logger.error(
            "Client session revocation failed: actor=%s target=%s reason=manual_revoke "
            "client_session=%s client_type=%s exception=%s",
            user_uuid(actor),
            user_uuid(getattr(session, "user", None)),
            session.pk,
            session.client_type,
            type(exc).__name__,
        )
        raise
    logger.info(
        "Client session revoked: actor=%s target=%s reason=manual_revoke "
        "client_session=%s client_type=%s count=%d",
        user_uuid(actor),
        user_uuid(getattr(session, "user", None)),
        session.pk,
        session.client_type,
        count,
    )
    return count
