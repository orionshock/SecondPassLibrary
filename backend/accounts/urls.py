from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .client_sessions.views import (
    CurrentUserClientSessionRevokeView,
    CurrentUserClientSessionsView,
)
from .views import (
    CurrentUserChangePasswordView,
    CurrentUserLogoutOtherWebSessionsView,
    CurrentUserView,
    ManagedUserResetPasswordView,
    ManagedUserViewSet,
    UserChoiceListView,
    UserProfileViewSet,
)

app_name = "accounts"

router = DefaultRouter()
router.register(r"profiles", UserProfileViewSet, basename="userprofile")
router.register(r"users", ManagedUserViewSet, basename="manageduser")

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="accounts_me"),
    path("user-choices/", UserChoiceListView.as_view(), name="user_choices"),
    path(
        "me/change-password/",
        CurrentUserChangePasswordView.as_view(),
        name="accounts_me_change_password",
    ),
    path(
        "me/web-sessions/logout-others/",
        CurrentUserLogoutOtherWebSessionsView.as_view(),
        name="accounts_me_web_sessions_logout_others",
    ),
    path(
        "me/client-sessions/",
        CurrentUserClientSessionsView.as_view(),
        name="accounts_me_client_sessions",
    ),
    path(
        "me/client-sessions/<str:session_id>/",
        CurrentUserClientSessionRevokeView.as_view(),
        name="accounts_me_client_sessions_revoke",
    ),
    path(
        "users/<str:profile_id>/reset-password/",
        ManagedUserResetPasswordView.as_view(),
        name="managed_user_reset_password",
    ),
    path("", include(router.urls)),
]
