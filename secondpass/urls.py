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

from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.http import Http404, JsonResponse
from django.shortcuts import redirect
from django.templatetags.static import static
from django.urls import include, path, re_path
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
    # Legacy Product UI transition mount. Keep before the unprefixed catch-all.
    path("legacy/", include(("web.urls", "web"), namespace="legacy")),
    # Product UI (Django templates; capability-driven client-side nav)
    path("", include(("web.urls", "web"), namespace="web")),
    path("api-auth/login/", web_views.login, name="login"),
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

if settings.SECOND_PASS_ENABLE_DJANGO_ADMIN:
    urlpatterns.append(path("admin/", admin.site.urls))


def _cover_media(request, path: str):
    """
    Serve public cover images from MEDIA_ROOT/covers in direct-server mode.

    Notes:
    - Cover images are public display assets and keep their stable /media/covers/
      URLs in direct-server usage.
    - Book files live under MEDIA_ROOT/books and must not be publicly served as
      raw media.
    """
    parts = path.replace("\\", "/").split("/")
    if ".." in parts or path.startswith("/"):
        raise Http404()
    return static_serve(
        request,
        path,
        document_root=Path(settings.MEDIA_ROOT) / "covers",
    )


urlpatterns += [
    # Keep cover URLs stable in direct-server mode without exposing all media.
    re_path(r"^media/covers/(?P<path>.*)$", _cover_media),
]
