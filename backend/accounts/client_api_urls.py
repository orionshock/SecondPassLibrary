from django.urls import path

from .client_api_views import (
    ClientApiDiscoveryView,
    ClientLoginRequestCreateView,
    ClientLoginRequestPollView,
    ClientPairingDecisionView,
    ClientPairingLookupView,
)

app_name = "client_api"

urlpatterns = [
    path("discovery/", ClientApiDiscoveryView.as_view(), name="client_api_discovery"),
    path("pairing/lookup/", ClientPairingLookupView.as_view(), name="client_pairing_lookup"),
    path("pairing/decision/", ClientPairingDecisionView.as_view(), name="client_pairing_decision"),
    path(
        "login-requests/",
        ClientLoginRequestCreateView.as_view(),
        name="client_api_login_requests_create",
    ),
    path(
        "login-requests/<str:login_request_id>/poll/",
        ClientLoginRequestPollView.as_view(),
        name="client_api_login_requests_poll",
    ),
]
