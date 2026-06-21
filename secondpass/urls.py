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
from django.urls import include, path, re_path
from django.conf import settings
from django.http import Http404
from django.templatetags.static import static
from django.views.generic.base import RedirectView
from django.views.static import serve as static_serve

from core.views import secondpass_well_known
from web import views as web_views

urlpatterns = [
    path(".well-known/secondpass", secondpass_well_known, name="secondpass_well_known"),
    path(
        "favicon.ico",
        RedirectView.as_view(url=static("web/favicon.png"), permanent=True),
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

def _debug_media(request, path: str):
    """
    Development convenience: serve MEDIA_ROOT at MEDIA_URL via Django only when DEBUG=True.

    Notes:
    - MEDIA_URL (default: /media/) is the canonical public URL prefix for user media
      like cover images.
    - In production, deployments should serve MEDIA_ROOT at MEDIA_URL via their web
      server/reverse proxy/static file layer, not Django.
    """
    if not settings.DEBUG:
        raise Http404()
    return static_serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [
    # Always register the route so generated URLs remain stable; it only serves
    # content when DEBUG=True.
    re_path(r"^media/(?P<path>.*)$", _debug_media),
]
