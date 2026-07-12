from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import include, path, resolve, reverse

from core import server_settings
from core.admin import ServerSettingAdmin
from core.models import ServerSetting
from core.server_settings import set_server_setting
from library.groups.consolidation import build_advanced_groups_disable_plan
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.groups.services import add_book_to_group, add_user_to_group
from library.models import LibraryGroup
from shelves.models import Shelf
from tests.testenv.filesystem import IsolatedMediaRootMixin
from tests.utils.books import create_file_backed_book


urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("web.urls")),
]


@override_settings(ROOT_URLCONF=__name__)
class AdvancedGroupsRecoveryAdminTests(IsolatedMediaRootMixin, TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_superuser(
            username="owner",
            password="pw",
        )
        self.staff = User.objects.create_user(
            username="staff",
            password="pw",
            is_staff=True,
        )
        self.public = LibraryGroup.objects.create(name="Configured Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        server_settings.set_advanced_library_groups_enabled(True)
        add_user_to_group(user=self.owner, group=self.public)
        add_user_to_group(user=self.staff, group=self.public)
        self.url = reverse("admin:core_serversetting_advanced_groups_disable")

    def _add_custom_state(self):
        group = LibraryGroup.objects.create(name="Club")
        reader = get_user_model().objects.create_user(username="reader")
        add_user_to_group(user=reader, group=group, is_curator=True)
        book = create_file_backed_book(
            title="Club Book",
            assign_public=False,
        ).book
        add_book_to_group(book=book, group=group)
        Shelf.objects.create(
            name="Club Shelf",
            owner_type=Shelf.OWNER_TYPE_GROUP,
            owner_group=group,
            created_by=self.owner,
        )
        return group

    def _login_owner(self):
        self.assertTrue(self.client.login(username="owner", password="pw"))

    def _confirmation(self, fingerprint):
        return {
            "fingerprint": fingerprint,
            "confirm": "on",
            "confirmation_text": "DISABLE ADVANCED GROUPS",
        }

    def test_superuser_preview_renders_plan_counts_and_confirmation_fields(self):
        self._add_custom_state()
        self._login_owner()

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Custom groups deleted: 1")
        self.assertContains(response, "Shelves moved: 1")
        self.assertContains(response, "Book/group associations removed: 1")
        self.assertContains(response, "Memberships removed: 1")
        self.assertContains(response, 'name="fingerprint"', html=False)
        self.assertContains(response, 'name="confirm"', html=False)
        self.assertContains(response, 'name="confirmation_text"', html=False)
        self.assertContains(response, "normal access-controlled LibraryGroup")

    def test_non_superuser_is_denied(self):
        self.assertTrue(self.client.login(username="staff", password="pw"))

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 403)

    def test_confirmation_fields_are_required(self):
        self._add_custom_state()
        self._login_owner()
        plan = build_advanced_groups_disable_plan()

        response = self.client.post(self.url, {"fingerprint": plan.fingerprint})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "This field is required.", count=2)
        self.assertTrue(server_settings.advanced_library_groups_enabled())

    def test_stale_fingerprint_is_rejected_with_recoverable_message(self):
        group = self._add_custom_state()
        self._login_owner()
        plan = build_advanced_groups_disable_plan()
        group.name = "Changed after preview"
        group.save(update_fields=["name", "updated_at"])

        response = self.client.post(
            self.url,
            self._confirmation(plan.fingerprint),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "state changed after preview")
        self.assertTrue(server_settings.advanced_library_groups_enabled())
        self.assertTrue(LibraryGroup.objects.filter(pk=group.pk).exists())

    def test_success_renders_completion_summary(self):
        self._add_custom_state()
        self._login_owner()
        plan = build_advanced_groups_disable_plan()

        response = self.client.post(
            self.url,
            self._confirmation(plan.fingerprint),
        )

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response,
            "admin/core/serversetting/advanced_groups_disable_complete.html",
        )
        self.assertContains(response, "Advanced library groups disabled")
        self.assertContains(response, "Custom groups deleted: 1")
        self.assertContains(response, "Shelves renamed and moved: 1")
        self.assertFalse(server_settings.advanced_library_groups_enabled())

    def test_already_disabled_and_enabled_without_custom_groups_render_safely(self):
        self._login_owner()
        enabled_response = self.client.get(self.url)
        self.assertContains(enabled_response, "Custom groups deleted: 0")

        plan = build_advanced_groups_disable_plan()
        completion = self.client.post(
            self.url,
            self._confirmation(plan.fingerprint),
        )
        self.assertEqual(completion.status_code, 200)
        self.assertContains(completion, "Custom groups deleted: 0")

        disabled_response = self.client.get(self.url)
        self.assertEqual(disabled_response.status_code, 200)
        self.assertContains(disabled_response, "already disabled")
        self.assertNotContains(disabled_response, 'name="confirmation_text"')

    def test_structural_setting_is_read_only_and_recovery_link_resolves(self):
        self._login_owner()
        setting = ServerSetting.objects.get(
            key=server_settings.ADVANCED_LIBRARY_GROUPS_SETTING
        )
        change_url = reverse("admin:core_serversetting_change", args=[setting.pk])

        response = self.client.get(change_url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Advanced Library Groups")
        self.assertContains(response, "Disable and consolidate into Public/Common Room")
        self.assertNotContains(response, 'name="key"')
        self.assertNotContains(response, 'name="value"')
        model_admin = ServerSettingAdmin(ServerSetting, admin.site)
        self.assertIn("key", model_admin.get_readonly_fields(response.wsgi_request, setting))
        self.assertIn("value", model_admin.get_readonly_fields(response.wsgi_request, setting))
        self.assertFalse(model_admin.has_add_permission(response.wsgi_request))
        self.assertEqual(
            resolve(self.url).url_name,
            "core_serversetting_advanced_groups_disable",
        )
