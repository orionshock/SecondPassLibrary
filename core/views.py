from django.conf import settings
from django.http import JsonResponse

from core import server_settings


def health_check(request):
    return JsonResponse({"status": "ok"})


def secondpass_well_known(request):
    """
    Minimal discovery document for external clients.

    This is intentionally simple and not OAuth/OIDC.
    """
    api_base = request.build_absolute_uri("/api/v1/")
    return JsonResponse(
        {
            "server_name": server_settings.get_server_name(),
            "server_description": server_settings.get_server_description(),
            "server_version": settings.SECOND_PASS_SERVER_VERSION,
            "server_release_date": settings.SECOND_PASS_SERVER_RELEASE_DATE,
            "api_base_url": api_base,
        }
    )
