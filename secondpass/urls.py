"""
URL configuration for secondpass project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from pathlib import Path
from django.urls import include, path, re_path
from django.conf import settings
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.templatetags.static import static
from django.views import defaults as default_views
from django.views.static import serve as static_serve

from core.views import secondpass_well_known
from web import views as web_views


def favicon(request):
    return redirect(static("web/favicon.png"), permanent=True)


def page_not_found(request, exception):
    if request.path.startswith("/api/"):
        return JsonResponse({"detail": "Not found."}, status=404)
    return default_views.page_not_found(request, exception, template_name="404.html")


handler404 = page_not_found


urlpatterns = [
    path(".well-known/secondpass", secondpass_well_known, name="secondpass_well_known"),
    path(
        "favicon.ico",
        favicon,
        name="favicon",
    ),
    # Product UI (Django templates; capability-driven client-side nav)
    path("", include(("web.urls", "web"), namespace="web")),
    path("api-auth/login/", web_views.login, name="login"),
    path("admin/", admin.site.urls),
    # API v1 (versioned, REST/JSON)
    path("api/v1/library/", include(("library.urls", "library"), namespace="library")),
    path(
        "api/v1/client-api/",
        include(("accounts.client_api_urls", "client_api"), namespace="client_api"),
    ),
    path(
        "api/v1/accounts/", include(("accounts.urls", "accounts"), namespace="accounts")
    ),
    path("api/v1/reading/", include(("reading.urls", "reading"), namespace="reading")),
    path("api/v1/shelves/", include(("shelves.urls", "shelves"), namespace="shelves")),
    path("api/v1/", include(("core.urls", "core"), namespace="core")),
    path("api-auth/", include("rest_framework.urls")),
]

def _media(request, path: str):
    """
    Serve public cover images directly, and broad MEDIA_ROOT only in DEBUG.

    Notes:
    - MEDIA_URL (default: /media/) is the canonical public URL prefix for user media
      like cover images.
    - Cover images are public display assets and keep their stable /media/covers/
      URLs in direct-server production-mode usage.
    - Other media paths can include protected EPUBs and are served by Django only
      as a DEBUG development convenience.
    """
    if path.startswith("covers/"):
        cover_path = path.removeprefix("covers/")
        parts = cover_path.replace("\\", "/").split("/")
        if ".." in parts or cover_path.startswith("/"):
            raise Http404()
        return static_serve(
            request,
            cover_path,
            document_root=Path(settings.MEDIA_ROOT) / "covers",
        )
    if not settings.DEBUG:
        raise Http404()
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [
    # Always register the route so generated URLs remain stable. Covers are
    # served in direct-server mode; other media is DEBUG-only.
    re_path(r"^media/(?P<path>.*)$", _media),
]
