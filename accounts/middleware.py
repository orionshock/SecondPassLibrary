from __future__ import annotations

from datetime import timedelta

from django.utils import timezone

from .models import UserWebSession


class UserWebSessionMiddleware:
    """
    Track authenticated Django web sessions via a companion `UserWebSession` row.

    This is tracking-only. Revocation still deletes rows from Django's session store.
    """

    # Simple write throttle: don't update last-seen more than once per minute unless
    # user agent / IP changes.
    THROTTLE_SECONDS = 60

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            user = getattr(request, "user", None)
            if not user or getattr(user, "is_anonymous", True):
                return response

            session = getattr(request, "session", None)
            if not session:
                return response

            session_key = getattr(session, "session_key", None) or ""
            if not session_key:
                # Avoid creating sessions unnecessarily.
                return response

            user_agent = (request.META.get("HTTP_USER_AGENT") or "")[:4000]
            ip_address = request.META.get("REMOTE_ADDR") or None

            now = timezone.now()
            defaults = {"user": user, "user_agent": user_agent, "ip_address": ip_address}

            obj, created = UserWebSession.objects.get_or_create(
                session_key=session_key,
                defaults=defaults,
            )

            if created:
                return response

            # Session keys can persist across logout/login; ensure ownership is correct.
            needs_save = False
            update_fields: list[str] = []

            if obj.user_id != user.id:
                obj.user = user
                needs_save = True
                update_fields.append("user")

            if (obj.user_agent or "") != user_agent:
                obj.user_agent = user_agent
                needs_save = True
                update_fields.append("user_agent")

            if obj.ip_address != ip_address:
                obj.ip_address = ip_address
                needs_save = True
                update_fields.append("ip_address")

            # Throttle last-seen updates.
            if obj.updated_at is None or (now - obj.updated_at) > timedelta(seconds=self.THROTTLE_SECONDS):
                needs_save = True

            if needs_save:
                # `updated_at` is auto_now; include it explicitly in update_fields so
                # Django performs an UPDATE even when only throttling.
                if "updated_at" not in update_fields:
                    update_fields.append("updated_at")
                obj.save(update_fields=update_fields)
        except Exception:
            # Best-effort tracking: do not block responses on tracking failures.
            return response

        return response

