from django.http import JsonResponse


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
            "server_name": "Second Pass Library",
            "api_base_url": api_base,
            "client_api": {
                "discovery_version": "0.1",
                "discovery_endpoint": request.build_absolute_uri("/api/v1/client-api/discovery/"),
                "login_request_endpoint": request.build_absolute_uri("/api/v1/client-api/login-requests/"),
                "authorize_url": request.build_absolute_uri("/client-api/authorize/"),
                "poll_endpoint_template": request.build_absolute_uri("/api/v1/client-api/login-requests/{id}/poll/"),
                "token_type": "Bearer",
            },
        }
    )
