from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import CurrentUserView, ManagedUserViewSet, UserProfileViewSet

app_name = "accounts"

router = DefaultRouter()
router.register(r"profiles", UserProfileViewSet, basename="userprofile")
router.register(r"users", ManagedUserViewSet, basename="manageduser")

urlpatterns = [
    path("me/", CurrentUserView.as_view(), name="accounts_me"),
    path("", include(router.urls)),
]
