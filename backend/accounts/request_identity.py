from __future__ import annotations

import ipaddress

from django.conf import settings


def get_client_ip(request) -> str | None:
    """Return the effective client IP under the trusted-proxy contract."""
    direct_ip = _normalize_ip(request.META.get("REMOTE_ADDR"))
    if not settings.TRUST_X_FORWARDED_FOR or direct_ip is None:
        return direct_ip

    trusted_proxy_ips = {
        normalized
        for value in settings.TRUSTED_PROXY_IPS
        if (normalized := _normalize_ip(value)) is not None
    }
    if direct_ip not in trusted_proxy_ips:
        return direct_ip

    forwarded_value = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0]
    return _normalize_ip(forwarded_value) or direct_ip


def _normalize_ip(value: object) -> str | None:
    try:
        address = ipaddress.ip_address(str(value or "").strip())
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(address)
    except ValueError:
        return None
