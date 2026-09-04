from django.contrib import admin
from django.contrib.auth import get_user_model
from django.test import RequestFactory, TestCase, override_settings
from django.urls import include, path, resolve, reverse

from core import server_settings
from core.admin import ServerSettingAdmin, ServerSettingAdminForm
from core.models import ServerSetting
from core.server_settings import set_server_setting
from library.groups.consolidation import build_advanced_groups_disable_plan
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.groups.memberships import add_user_to_group
from library.groups.book_assignments import add_book_to_group
from library.models import BookGroupAssignment, LibraryGroup, LibraryGroupMembership
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

    def test_semantic_labels_and_copy_replace_generic_value_presentation(self):
        server_settings.ensure_editable_server_settings()
        expected = {
            server_settings.SERVER_NAME_SETTING: (
                "Server Name",
                "Display name used in Product UI and discovery.",
            ),
            server_settings.SERVER_DESCRIPTION_SETTING: (
                "Server Description",
                "Description used in discovery and server identity.",
            ),
            server_settings.SERVER_BANNER_MESSAGE_SETTING: (
                "Server Banner Message",
                "Banner message shown in Product UI.",
            ),
        }

        for key, (label, help_text) in expected.items():
            with self.subTest(key=key):
                form = ServerSettingAdminForm(
                    instance=ServerSetting.objects.get(key=key)
                )
                self.assertEqual(form.fields["value"].label, label)
                self.assertEqual(form.fields["value"].help_text, help_text)

    def test_structural_settings_cannot_be_deleted_or_bulk_deleted(self):
        model_admin = ServerSettingAdmin(ServerSetting, admin.site)
        request = RequestFactory().get("/admin/core/serversetting/")
        request.user = self.owner
        advanced = ServerSetting.objects.get(
            key=server_settings.ADVANCED_LIBRARY_GROUPS_SETTING
        )
        public = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)

        self.assertFalse(model_admin.has_delete_permission(request, advanced))
        self.assertFalse(model_admin.has_delete_permission(request, public))
        self.assertIsNone(model_admin.actions)

    def test_public_group_page_uses_semantic_selector_and_current_copy(self):
        self._login_owner()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)

        response = self.client.get(
            reverse("admin:core_serversetting_change", args=[setting.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public/Common Room Group")
        self.assertContains(response, "configured protected Public/Common Room identity")
        self.assertContains(response, "Confirm Public/Common Room reassignment")
        self.assertContains(response, "Repair Public/Common Room identity")
        self.assertContains(response, "public_group_id")
        self.assertNotContains(response, "rewrite")
        self.assertNotContains(response, "branch")

    def test_public_group_reassignment_requires_confirmation(self):
        self._login_owner()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        other = LibraryGroup.objects.create(name="Other Room")
        change_url = reverse("admin:core_serversetting_change", args=[setting.pk])

        response = self.client.post(change_url, {"value": str(other.pk), "_save": "Save"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Confirm the Public/Common Room reassignment")
        setting.refresh_from_db()
        self.assertEqual(setting.value, str(self.public.pk))

    def test_safe_public_group_reassignment_uses_selected_library_group(self):
        self._login_owner()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        other = LibraryGroup.objects.create(name="Other Room")

        response = self.client.post(
            reverse("admin:core_serversetting_change", args=[setting.pk]),
            {
                "value": str(other.pk),
                "confirm_public_reassignment": "on",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 302)
        setting.refresh_from_db()
        self.assertEqual(setting.value, str(other.pk))
        self.assertTrue(LibraryGroup.objects.filter(pk=self.public.pk).exists())

    def test_unsafe_public_group_reassignment_with_curator_is_blocked(self):
        self._login_owner()
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        other = LibraryGroup.objects.create(name="Curated Room")
        LibraryGroupMembership.objects.create(
            user=self.staff,
            group=other,
            is_curator=True,
        )

        response = self.client.post(
            reverse("admin:core_serversetting_change", args=[setting.pk]),
            {
                "value": str(other.pk),
                "confirm_public_reassignment": "on",
                "_save": "Save",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Remove curator memberships")
        setting.refresh_from_db()
        self.assertEqual(setting.value, str(self.public.pk))

    def test_public_group_repair_action_creates_fresh_identity(self):
        self._login_owner()
        previous_id = self.public.pk
        repair_url = reverse("admin:core_serversetting_public_group_repair")
        orphan_user = get_user_model().objects.create_user(username="orphan")
        orphan_book = create_file_backed_book(
            title="Orphan Book",
            assign_public=False,
        ).book

        get_response = self.client.get(repair_url)
        self.assertContains(get_response, "Create a new Common Room")
        response = self.client.post(
            repair_url,
            {"create_new_common_room": "on"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertNotEqual(setting.value, str(previous_id))
        self.assertTrue(LibraryGroup.objects.filter(pk=previous_id).exists())
        new_public = LibraryGroup.objects.get(pk=setting.value)
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=orphan_user,
                group=new_public,
                is_curator=False,
            ).exists()
        )
        self.assertTrue(
            orphan_book.group_assignments.filter(group=new_public).exists()
        )
        self.assertContains(response, "Created Public/Common Room identity")
        self.assertContains(response, "Restored 1 user(s) and 1 book(s)")

    def test_public_group_repair_uses_current_identity_when_new_not_selected(self):
        self._login_owner()
        orphan_user = get_user_model().objects.create_user(username="orphan")
        orphan_book = create_file_backed_book(
            title="Orphan Book",
            assign_public=False,
        ).book

        response = self.client.post(
            reverse("admin:core_serversetting_public_group_repair"),
            {},
            follow=True,
        )

        setting = ServerSetting.objects.get(key=PUBLIC_GROUP_ID_SETTING)
        self.assertEqual(setting.value, str(self.public.pk))
        self.assertTrue(
            LibraryGroupMembership.objects.filter(
                user=orphan_user,
                group=self.public,
                is_curator=False,
            ).exists()
        )
        self.assertTrue(
            orphan_book.group_assignments.filter(group=self.public).exists()
        )
        self.assertContains(response, "Verified Public/Common Room identity")
        self.assertContains(response, "Restored 1 user(s) and 1 book(s)")

    def test_disabled_setting_shows_status_without_recovery_action(self):
        self._login_owner()
        server_settings.set_advanced_library_groups_enabled(False)
        setting = ServerSetting.objects.get(
            key=server_settings.ADVANCED_LIBRARY_GROUPS_SETTING
        )

        response = self.client.get(
            reverse("admin:core_serversetting_change", args=[setting.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Disabled")
        self.assertNotContains(response, "Recovery guidance")
        self.assertNotContains(response, "Recovery action")
        self.assertNotContains(
            response,
            "Disable and consolidate into Public/Common Room",
        )

    def test_disabled_state_keeps_assignment_admin_sections_unregistered(self):
        self._login_owner()
        server_settings.set_advanced_library_groups_enabled(False)

        index = self.client.get(reverse("admin:index"))
        self.assertNotContains(index, "User Group Assignments")
        self.assertNotContains(index, "Book Group Assignments")
        self.assertNotIn(LibraryGroupMembership, admin.site._registry)
        self.assertNotIn(BookGroupAssignment, admin.site._registry)

    def test_disabled_state_book_delete_allows_related_assignment_cleanup(self):
        self._login_owner()
        server_settings.set_advanced_library_groups_enabled(False)
        book = create_file_backed_book(title="Delete Me", assign_public=False).book
        assignment = add_book_to_group(book=book, group=self.public)

        confirm = self.client.get(reverse("admin:library_book_delete", args=[book.pk]))
        self.assertEqual(confirm.status_code, 200)
        response = self.client.post(
            reverse("admin:library_book_delete", args=[book.pk]),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(type(book).objects.filter(pk=book.pk).exists())
        self.assertFalse(BookGroupAssignment.objects.filter(pk=assignment.pk).exists())

    def test_disabled_state_user_delete_allows_related_membership_cleanup(self):
        self._login_owner()
        server_settings.set_advanced_library_groups_enabled(False)
        user = get_user_model().objects.create_user(username="delete-me")
        membership = add_user_to_group(user=user, group=self.public)

        confirm = self.client.get(reverse("admin:auth_user_delete", args=[user.pk]))
        self.assertEqual(confirm.status_code, 200)
        response = self.client.post(
            reverse("admin:auth_user_delete", args=[user.pk]),
            {"post": "yes"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertFalse(get_user_model().objects.filter(pk=user.pk).exists())
        self.assertFalse(LibraryGroupMembership.objects.filter(pk=membership.pk).exists())

    def test_enabled_state_keeps_assignment_admin_sections_unregistered(self):
        self._login_owner()

        index = self.client.get(reverse("admin:index"))

        self.assertNotContains(index, "User Group Assignments")
        self.assertNotContains(index, "Book Group Assignments")
        self.assertNotIn(LibraryGroupMembership, admin.site._registry)
        self.assertNotIn(BookGroupAssignment, admin.site._registry)
