from __future__ import annotations

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

from core.server_settings import normalize_second_pass_reader_web_client_url


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

    if settings.SECURE_PROXY_SSL_HEADER == ("HTTP_X_FORWARDED_PROTO", "https") and (
        not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE
    ):
        messages.append(
            Error(
                "Forwarded HTTPS proxy trust requires secure session and CSRF cookies.",
                hint=(
                    "Set DJANGO_SECURE_COOKIES=1 for HTTPS reverse-proxy deployments."
                ),
                id="secondpass.E002",
            )
        )

    return messages


@register()
def second_pass_reader_web_client_url_check(_app_configs=None, **_kwargs):
    value = str(settings.SECOND_PASS_READER_WEB_CLIENT_URL or "").strip()
    if not value:
        return []
    try:
        normalize_second_pass_reader_web_client_url(value)
    except ValueError as exc:
        return [
            Error(
                f"SECOND_PASS_READER_WEB_CLIENT_URL is invalid: {exc}",
                id="secondpass.E001",
            )
        ]
    return []
