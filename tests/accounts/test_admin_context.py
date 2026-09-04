from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory, TestCase, override_settings
from django.urls import path, reverse

from accounts.admin import UserProfileInline
from accounts.models import UserClientSession, UserProfile, UserWebSession
from library.models import Book, LibraryGroup, LibraryGroupMembership
from marginalia.models import ReadingSession


urlpatterns = [path("admin/", admin.site.urls)]


@override_settings(ROOT_URLCONF=__name__)
class UserAdminContextTests(TestCase):
    def setUp(self):
        self.operator = User.objects.create_superuser(
            username="operator",
            password="pw",
        )
        self.target = User.objects.create_user(username="reader", password="pw")
        self.other = User.objects.create_user(username="other", password="pw")
        self.client.force_login(self.operator)

    def test_user_page_combines_profile_memberships_and_related_navigation(self):
        group = LibraryGroup.objects.create(name="Readers")
        membership = LibraryGroupMembership.objects.create(
            user=self.target,
            group=group,
            is_curator=True,
        )

        response = self.client.get(
            reverse("admin:auth_user_change", args=[self.target.pk])
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Profile")
        self.assertContains(response, 'name="profile-0-role"')
        self.assertContains(response, "Library Group memberships")
        membership_url = reverse(
            "admin:library_librarygroupmembership_change",
            args=[membership.pk],
        )
        group_url = reverse("admin:library_librarygroup_change", args=[group.pk])
        self.assertContains(response, f'href="{group_url}">Readers</a>')
        self.assertContains(response, f'href="{membership_url}">Curator</a>')
        self.assertNotContains(response, str(membership))
        self.assertNotContains(response, "column-created_at")
        self.assertNotContains(response, "column-membership_link")
        for route in (
            "admin:marginalia_readingsession_changelist",
            "admin:accounts_userclientsession_changelist",
            "admin:accounts_userwebsession_changelist",
        ):
            self.assertContains(response, reverse(route))
            self.assertContains(response, f"user__id__exact={self.target.pk}")

    def test_profile_inline_persists_profile_fields(self):
        request = RequestFactory().post("/admin/auth/user/")
        request.user = self.operator
        inline = UserProfileInline(User, admin.site)
        FormSet = inline.get_formset(request, obj=self.target)
        prefix = FormSet.get_default_prefix()
        profile = self.target.profile
        formset = FormSet(
            data={
                f"{prefix}-TOTAL_FORMS": "1",
                f"{prefix}-INITIAL_FORMS": "1",
                f"{prefix}-MIN_NUM_FORMS": "0",
                f"{prefix}-MAX_NUM_FORMS": "1",
                f"{prefix}-0-id": str(profile.pk),
                f"{prefix}-0-user": str(self.target.pk),
                f"{prefix}-0-role": UserProfile.ROLE_LIBRARIAN,
                f"{prefix}-0-must_change_password": "on",
            },
            instance=self.target,
            prefix=prefix,
        )

        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        profile.refresh_from_db()
        self.assertEqual(profile.role, UserProfile.ROLE_LIBRARIAN)
        self.assertTrue(profile.must_change_password)

    def test_session_changelists_filter_to_one_user_without_changing_default_list(self):
        UserWebSession.objects.create(user=self.target, session_key="target-web")
        UserWebSession.objects.create(user=self.other, session_key="other-web")
        UserClientSession.objects.create(
            user=self.target,
            name="Target Reader",
            client_type="android",
            token_hash="a" * 64,
        )
        UserClientSession.objects.create(
            user=self.other,
            name="Other Reader",
            client_type="android",
            token_hash="b" * 64,
        )
        book = Book.objects.create(title="Context Book")
        ReadingSession.objects.create(user=self.target, book=book)
        other_book = Book.objects.create(title="Other Context Book")
        ReadingSession.objects.create(user=self.other, book=other_book)

        for route in (
            "admin:accounts_userwebsession_changelist",
            "admin:accounts_userclientsession_changelist",
            "admin:marginalia_readingsession_changelist",
        ):
            base_url = reverse(route)
            filtered = self.client.get(
                base_url,
                {"user__id__exact": self.target.pk},
            )
            unfiltered = self.client.get(base_url)

            self.assertEqual(filtered.status_code, 200)
            self.assertEqual(
                {row.user_id for row in filtered.context["cl"].result_list},
                {self.target.pk},
            )
            unfiltered_user_ids = {
                row.user_id for row in unfiltered.context["cl"].result_list
            }
            self.assertTrue({self.target.pk, self.other.pk} <= unfiltered_user_ids)

    def test_standalone_profile_admin_remains_registered(self):
        self.assertIn(UserProfile, admin.site._registry)
        response = self.client.get(reverse("admin:accounts_userprofile_changelist"))
        self.assertEqual(response.status_code, 200)
