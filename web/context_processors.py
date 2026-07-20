from __future__ import annotations

from django.http import HttpRequest


def product_ui_mount(request: HttpRequest) -> dict[str, str]:
    resolver_match = request.resolver_match
    prefix = "/legacy" if resolver_match and resolver_match.namespace == "legacy" else ""
    return {"product_ui_prefix": prefix}
