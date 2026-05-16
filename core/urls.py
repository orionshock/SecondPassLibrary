from django.urls import path

from .views import health_check
from .api_views import ServerSettingsView

app_name = "core"

urlpatterns = [
    path("health/", health_check, name="health_check"),
    path("server/settings/", ServerSettingsView.as_view(), name="server_settings"),
]
