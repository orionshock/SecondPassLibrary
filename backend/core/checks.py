from __future__ import annotations

from collections import Counter
from ipaddress import collapse_addresses
from pathlib import Path
import re

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

from accounts.request_identity import trusted_proxy_network
from core.server_settings import normalize_second_pass_reader_web_client_url


_PLACEHOLDER_ALLOWED_HOSTS = {"your-hostname-or-domain"}
_HOSTNAME_RE = re.compile(r"^[A-Za-z0-9.-]+$")


def _valid_allowed_host(value: object) -> bool:
    host = str(value or "")
    if not host or host != host.strip():
        return False
    if host == "*":
        return True
    if host.startswith("."):
        host = host[1:]
    if host.startswith("[") and host.endswith("]"):
        network = trusted_proxy_network(host[1:-1])
        return network is not None and network.version == 6 and network.num_addresses == 1
    if ":" in host or not _HOSTNAME_RE.fullmatch(host) or len(host) > 253:
        return False
    labels = host.rstrip(".").split(".")
    return all(
        label
        and len(label) <= 63
        and not label.startswith("-")
        and not label.endswith("-")
        for label in labels
    )


def _paths_overlap(first: Path, second: Path) -> bool:
    return first == second or first in second.parents or second in first.parents


@register(Tags.security, deploy=True)
def production_security_settings_check(_app_configs=None, **_kwargs):
    messages = []

    if settings.DEBUG:
        messages.append(
            Error(
                "DEBUG is enabled during a deployment check.",
                hint=(
                    "Set DJANGO_DEBUG=0 for deployed instances. Use the development "
                    "startup path when debug behavior is intentional."
                ),
                id="secondpass.E003",
            )
        )
    else:
        allowed_hosts = list(settings.ALLOWED_HOSTS)
        if "*" in allowed_hosts:
            messages.append(
                Error(
                    "ALLOWED_HOSTS disables host validation while DEBUG=False.",
                    hint=(
                        "Remove '*'. List the Second Pass Library server hostnames "
                        "or IP addresses users enter in their URLs, not client-device "
                        "addresses."
                    ),
                    id="secondpass.E004",
                )
            )
        if not allowed_hosts:
            messages.append(
                Error(
                    "ALLOWED_HOSTS does not name this Second Pass Library server.",
                    hint=(
                        "List the server hostnames or IP addresses users enter in "
                        "their URLs, not the addresses of connecting client devices."
                    ),
                    id="secondpass.E005",
                )
            )
        if _PLACEHOLDER_ALLOWED_HOSTS.intersection(allowed_hosts):
            messages.append(
                Error(
                    "ALLOWED_HOSTS still contains the packaged placeholder.",
                    hint=(
                        "Replace it with the Second Pass Library server hostnames or "
                        "IP addresses users enter in their URLs, not client-device "
                        "addresses."
                    ),
                    id="secondpass.E006",
                )
            )
        if any(not _valid_allowed_host(value) for value in allowed_hosts):
            messages.append(
                Error(
                    "ALLOWED_HOSTS contains a malformed host value.",
                    hint=(
                        "List this server's hostnames, IPv4 addresses, or bracketed "
                        "IPv6 addresses without schemes, paths, or ports. Do not list "
                        "client-device addresses."
                    ),
                    id="secondpass.E007",
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

    if not settings.DEBUG and settings.USE_X_FORWARDED_HOST:
        messages.append(
            Warning(
                "Forwarded host trust is enabled.",
                hint=(
                    "Keep DJANGO_USE_X_FORWARDED_HOST=0 unless the proxy replaces "
                    "X-Forwarded-Host and the application port is private."
                ),
                id="secondpass.W003",
            )
        )

    return messages


@register(Tags.security)
def trusted_proxy_settings_check(_app_configs=None, **_kwargs):
    values = list(settings.TRUSTED_PROXY_IPS)
    parsed = [trusted_proxy_network(value) for value in values]
    messages = []

    if any(network is None for network in parsed):
        messages.append(
            Error(
                "TRUSTED_PROXY_IPS contains an invalid IP address or CIDR network.",
                hint=(
                    "Set DJANGO_TRUSTED_PROXY_IPS to direct proxy peer addresses or "
                    "CIDR networks."
                ),
                id="secondpass.E008",
            )
        )

    valid_networks = [network for network in parsed if network is not None]
    canonical = [network.with_prefixlen for network in valid_networks]
    if any(count > 1 for count in Counter(canonical).values()):
        messages.append(
            Warning(
                "TRUSTED_PROXY_IPS contains duplicate proxy networks.",
                hint="Remove duplicate DJANGO_TRUSTED_PROXY_IPS entries.",
                id="secondpass.W002",
            )
        )

    if settings.TRUST_X_FORWARDED_FOR and not values:
        messages.append(
            Error(
                "Forwarded client-IP trust is enabled without a trusted proxy peer.",
                hint=(
                    "Set DJANGO_TRUSTED_PROXY_IPS to the direct proxy peers, or set "
                    "DJANGO_TRUST_X_FORWARDED_FOR=0."
                ),
                id="secondpass.E009",
            )
        )

    if settings.TRUST_X_FORWARDED_FOR and _includes_trust_all(valid_networks):
        messages.append(
            Error(
                "Forwarded client-IP trust accepts every direct peer.",
                hint=(
                    "Replace trust-all CIDRs with the direct proxy peer addresses or "
                    "private deployment networks."
                ),
                id="secondpass.E010",
            )
        )

    return messages


def _includes_trust_all(networks) -> bool:
    for version in (4, 6):
        same_version = [network for network in networks if network.version == version]
        if any(network.prefixlen == 0 for network in collapse_addresses(same_version)):
            return True
    return False


@register(Tags.security)
def storage_path_separation_check(_app_configs=None, **_kwargs):
    media_root = Path(settings.MEDIA_ROOT).resolve(strict=False)
    static_root = Path(settings.STATIC_ROOT).resolve(strict=False)
    if not _paths_overlap(media_root, static_root):
        return []
    return [
        Error(
            "MEDIA_ROOT and STATIC_ROOT overlap.",
            hint=(
                "Keep persistent media outside the collected static tree so stored "
                "EPUBs cannot become public static files."
            ),
            id="secondpass.E011",
        )
    ]


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
