import os

from django.conf import settings
from django.db import DatabaseError, connections
from django.http import JsonResponse
from django.views.decorators.http import require_safe

from core import server_settings


def _database_is_ready() -> bool:
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except (DatabaseError, OSError):
        return False
    return True


def _react_ui_is_ready() -> bool:
    return (settings.PRODUCT_UI_DIR / "index.html").is_file()


def _userdata_is_ready() -> bool:
    required_directories = (
        settings.USERDATA_DIR,
        settings.USERDATA_DIR / "db",
        settings.USERDATA_DIR / "media",
        settings.USERDATA_DIR / "imports",
    )
    return all(
        directory.is_dir() and os.access(directory, os.W_OK | os.X_OK)
        for directory in required_directories
    )


@require_safe
def health_check(request):
    checks = {
        "database": _database_is_ready(),
        "product_ui": _react_ui_is_ready(),
        "userdata": _userdata_is_ready(),
    }
    ready = all(checks.values())
    return JsonResponse(
        {
            "status": "ok" if ready else "unavailable",
            "checks": checks,
        },
        status=200 if ready else 503,
    )


@require_safe
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
