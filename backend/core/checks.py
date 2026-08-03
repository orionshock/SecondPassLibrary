from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

from core.server_settings import normalize_reading_client_base_url


@register(Tags.security, deploy=True)
def production_security_settings_check(_app_configs=None, **_kwargs):
    if settings.DEBUG:
        return []

    messages = []

    if settings.ALLOWED_HOSTS == ["*"]:
        messages.append(
            Warning(
                "ALLOWED_HOSTS uses wildcard host matching while DEBUG=False.",
                hint=(
                    "Set DJANGO_ALLOWED_HOSTS to the real production hostnames or "
                    "LAN IP addresses."
                ),
                id="secondpass.W001",
            )
        )

    if (
        settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https")
        and not settings.SESSION_COOKIE_SECURE
        and not settings.CSRF_COOKIE_SECURE
    ):
        messages.append(
            Warning(
                "Forwarded HTTPS proxy trust is enabled but secure cookies are off.",
                hint=(
                    "Set DJANGO_SECURE_COOKIES=1 for HTTPS reverse-proxy "
                    "deployments."
                ),
                id="secondpass.W002",
            )
        )

    return messages


@register()
def reading_client_base_url_check(_app_configs=None, **_kwargs):
    value = str(settings.SECOND_PASS_READING_CLIENT_BASE_URL or "").strip()
    if not value:
        return []
    try:
        normalize_reading_client_base_url(value)
    except ValueError as exc:
        return [
            Error(
                f"SECOND_PASS_READING_CLIENT_BASE_URL is invalid: {exc}",
                id="secondpass.E001",
            )
        ]
    return []
