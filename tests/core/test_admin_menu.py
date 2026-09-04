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

    def test_menu_uses_operator_workflow_groups_and_labels(self):
        app_list = admin.site.get_app_list(self.request)

        self.assertEqual(
            [app["name"] for app in app_list],
            ["Core", "Library", "UserData", "Maintenance"],
        )
        self.assertEqual(
            [[model["name"] for model in app["models"]] for app in app_list],
            [
                [
                    "Server Settings",
                    "Users",
                    "Web Session Management",
                    "Client Session Management",
                    "Client Login Request",
                ],
                ["Catalog Tags", "Library Groups", "Books", "Authors", "Series"],
                ["Shelves", "Reading Sessions", "Import Stage Management"],
                ["Tasks", "Run Log"],
            ],
        )

    def test_grouped_models_keep_their_existing_admin_urls(self):
        models = {
            model["object_name"]: model
            for app in admin.site.get_app_list(self.request)
            for model in app["models"]
        }

        self.assertEqual(models["User"]["admin_url"], "/admin/auth/user/")
        self.assertEqual(models["Shelf"]["admin_url"], "/admin/shelves/shelf/")
        self.assertEqual(
            models["ReadingSession"]["admin_url"],
            "/admin/marginalia/readingsession/",
        )

    def test_real_app_indexes_resolve_to_their_operator_group(self):
        accounts = admin.site.get_app_list(self.request, app_label="accounts")
        marginalia = admin.site.get_app_list(self.request, app_label="marginalia")

        self.assertEqual([app["name"] for app in accounts], ["Core"])
        self.assertEqual([app["name"] for app in marginalia], ["UserData"])
