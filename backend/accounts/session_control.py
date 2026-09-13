from __future__ import annotations

from dataclasses import dataclass

from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from accounts.operational_logging import logger, user_uuid
from core.operational_logging import info_on_commit

from .models import UserClientSession, UserProfile, UserWebSession


WEB_SESSION_GENERATION_KEY = "_second_pass_web_session_generation"


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

    with transaction.atomic():
        _advance_web_session_generation(user)
        return _delete_tracked_web_sessions(user=user)


def revoke_other_web_sessions(
    user,
    current_session=None,
    *,
    actor=None,
    reason: str = "manual_revoke",
    log_event: bool = True,
    log_failure: bool = True,
) -> int:
    """
    Revoke all tracked Django web sessions for the given user except the current session.

    If `current_session` is missing, this revokes all tracked sessions. The
    generation change also invalidates any valid session that lacks tracking.
    """
    try:
        with transaction.atomic():
            generation = _advance_web_session_generation(user)
            current_session_key = getattr(current_session, "session_key", None)
            count = _delete_tracked_web_sessions(
                user=user,
                preserved_session_key=current_session_key,
            )
            if current_session is not None and current_session_key:
                current_session[WEB_SESSION_GENERATION_KEY] = generation
                current_session.save()
    except Exception as exc:
        if log_failure:
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
    log_failure: bool = True,
) -> int:
    """
    Revoke all Client API bearer sessions for the given user.
    """
    if not user or getattr(user, "is_anonymous", False):
        return 0

    now = timezone.now()
    try:
        count = UserClientSession.objects.filter(
            user=user, revoked_at__isnull=True
        ).update(revoked_at=now, updated_at=now)
    except Exception as exc:
        if log_failure:
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


def user_changed_own_password(user, current_session=None) -> SessionRevocationCounts:
    web_count = revoke_other_web_sessions(
        user,
        current_session,
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
    try:
        web_count = revoke_other_web_sessions(
            user,
            None,
            actor=actor,
            reason="user_disabled",
            log_event=False,
            log_failure=False,
        )
    except Exception as exc:
        logger.error(
            "Managed user disable failed: operation=managed_user_disable "
            "actor=%s target=%s lifecycle_stage=web_session_revocation "
            "transaction=rolled_back retryable=true exception=%s",
            user_uuid(actor),
            user_uuid(user),
            type(exc).__name__,
        )
        raise
    try:
        client_count = revoke_all_api_sessions(
            user,
            actor=actor,
            reason="user_disabled",
            log_event=False,
            log_failure=False,
        )
    except Exception as exc:
        logger.error(
            "Managed user disable failed: operation=managed_user_disable "
            "actor=%s target=%s lifecycle_stage=client_session_revocation "
            "transaction=rolled_back retryable=true exception=%s",
            user_uuid(actor),
            user_uuid(user),
            type(exc).__name__,
        )
        raise
    info_on_commit(
        logger,
        "Sessions revoked: actor=%s target=%s reason=user_disabled "
        "web_sessions=%d client_sessions=%d",
        user_uuid(actor),
        user_uuid(user),
        web_count,
        client_count,
    )
    return SessionRevocationCounts(web_sessions=web_count, client_sessions=client_count)


def _advance_web_session_generation(user) -> int:
    # Deleting tracked rows is insufficient: generation also revokes valid browser
    # sessions created before tracking existed or tracking completed.
    profile = UserProfile.objects.select_for_update().get(user=user)
    profile.web_session_generation += 1
    profile.save(update_fields=["web_session_generation", "updated_at"])
    return profile.web_session_generation


def _delete_tracked_web_sessions(
    *, user, preserved_session_key: str | None = None
) -> int:
    tracked = UserWebSession.objects.filter(user=user)
    if preserved_session_key:
        tracked = tracked.exclude(session_key=preserved_session_key)
    keys = list(tracked.values_list("session_key", flat=True))
    if keys:
        Session.objects.filter(session_key__in=keys).delete()
    deleted, _ = tracked.delete()
    return deleted


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
