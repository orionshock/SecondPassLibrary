from __future__ import annotations

import ipaddress

from django.conf import settings


def get_client_ip(request) -> str | None:
    """Return the effective client IP under the trusted-proxy contract."""
    direct_ip = _normalize_ip(request.META.get("REMOTE_ADDR"))
    if not settings.TRUST_X_FORWARDED_FOR or direct_ip is None:
        return direct_ip

    direct_address = ipaddress.ip_address(direct_ip)
    trusted_proxy_networks = [
        network
        for value in settings.TRUSTED_PROXY_IPS
        if (network := trusted_proxy_network(value)) is not None
    ]
    if not any(direct_address in network for network in trusted_proxy_networks):
        return direct_ip

    forwarded_value = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",", 1)[0]
    return _normalize_ip(forwarded_value) or direct_ip


def trusted_proxy_network(value: object):
    """Parse one trusted direct-proxy IP or CIDR network."""
    try:
        return ipaddress.ip_network(str(value or "").strip(), strict=False)
    except ValueError:
        return None


def _normalize_ip(value: object) -> str | None:
    try:
        address = ipaddress.ip_address(str(value or "").strip())
        if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped:
            return str(address.ipv4_mapped)
        return str(address)
    except ValueError:
        return None
