from __future__ import annotations

import ipaddress

from django.conf import settings


MAX_FORWARDED_FOR_HOPS = 10


def canonical_client_ip(request) -> str | None:
    """Return the client IP under the project's single trusted-proxy contract."""
    direct_ip = normalize_ip(request.META.get("REMOTE_ADDR"))
    if not settings.TRUST_X_FORWARDED_FOR or direct_ip is None:
        return direct_ip

    trusted_proxy_ips = {
        normalized
        for value in settings.TRUSTED_PROXY_IPS
        if (normalized := normalize_ip(value)) is not None
    }
    if direct_ip not in trusted_proxy_ips:
        return direct_ip

    forwarded_values = [
        value.strip()
        for value in (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")
    ]
    if not forwarded_values or len(forwarded_values) > MAX_FORWARDED_FOR_HOPS:
        return direct_ip
    forwarded_ips = [normalize_ip(value) for value in forwarded_values]
    if any(value is None for value in forwarded_ips):
        return direct_ip

    for candidate in reversed([*forwarded_ips, direct_ip]):
        if candidate not in trusted_proxy_ips:
            return candidate
    return direct_ip


def normalize_ip(value: object) -> str | None:
    try:
        address = ipaddress.ip_address(str(value or "").strip())
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(address)
    except ValueError:
        return None
