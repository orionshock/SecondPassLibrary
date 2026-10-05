from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from accounts.models import UserWebSession


_LAST_SEEN_INTERVAL = timedelta(seconds=60)


def track_web_session(
    *, session_key: str, user_id: int, user_agent: str, ip_address: str | None
) -> None:
    """Persist observed browser-session facts without managing authentication.

    Metadata and ownership changes always advance last-seen; unchanged sessions
    advance it only after the write interval. Persistence errors reach the caller
    so the HTTP adapter can keep tracking best effort.
    """
    now = timezone.now()
    session, created = UserWebSession.objects.get_or_create(
        session_key=session_key,
        defaults={
            "user_id": user_id,
            "user_agent": user_agent,
            "ip_address": ip_address,
        },
    )
    if created:
        return

    # A persistent session key may be observed under a different account.
    update_fields: list[str] = []
    if session.user_id != user_id:
        session.user_id = user_id
        update_fields.append("user")
    if (session.user_agent or "") != user_agent:
        session.user_agent = user_agent
        update_fields.append("user_agent")
    if session.ip_address != ip_address:
        session.ip_address = ip_address
        update_fields.append("ip_address")

    if update_fields or session.updated_at is None or now - session.updated_at > _LAST_SEEN_INTERVAL:
        # auto_now must be included even for a last-seen-only UPDATE.
        update_fields.append("updated_at")
        session.save(update_fields=update_fields)
