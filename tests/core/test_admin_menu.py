from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class AdminMenuTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_superuser(
            username="menu-owner",
            password="pw",
        )
        self.request = RequestFactory().get("/admin/")
        self.request.user = self.user

    def test_menu_exposes_operator_workflows_without_internal_relationship_models(self):
        app_list = admin.site.get_app_list(self.request)
        models = {
            model["object_name"]: model
            for app in app_list
            for model in app["models"]
        }

        required_workflows = {
            "ServerSetting",
            "User",
            "UserWebSession",
            "UserClientSession",
            "ClientLoginRequest",
            "CatalogTag",
            "LibraryGroup",
            "Book",
            "Author",
            "Series",
            "Shelf",
            "ReadingSession",
            "ImportStage",
            "MaintenanceTaskConfig",
            "MaintenanceTaskRun",
        }
        self.assertTrue(required_workflows.issubset(models))
        self.assertTrue(all(models[name].get("admin_url") for name in required_workflows))
        self.assertTrue(
            {"UserProfile", "ExternalIdentity", "ShelfItem", "Annotation"}.isdisjoint(
                models
            )
        )
