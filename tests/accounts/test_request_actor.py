from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.test import RequestFactory, TestCase
from django.test.utils import CaptureQueriesContext

from accounts.models import UserProfile
from accounts.request_actor import get_request_actor_context


User = get_user_model()


class RequestActorContextTests(TestCase):
    def test_context_reuses_django_user_and_loads_profile_facts_once(self):
        user = User.objects.create_user(
            username="actor",
            password="pw",
            first_name="Ada",
            last_name="Lovelace",
        )
        profile = UserProfile.objects.get(user=user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.must_change_password = True
        profile.web_session_generation = 7
        profile.save(
            update_fields=[
                "role",
                "must_change_password",
                "web_session_generation",
                "updated_at",
            ]
        )
        request = RequestFactory().get("/")
        request.user = user

        with CaptureQueriesContext(connection) as captured:
            actor = get_request_actor_context(request)
            reused_actor = get_request_actor_context(request)

        self.assertEqual(len(captured), 1)
        self.assertIn('"accounts_userprofile"', captured[0]["sql"])
        self.assertNotIn('"auth_user"', captured[0]["sql"])
        self.assertIs(actor, reused_actor)
        self.assertEqual(actor.user_id, user.pk)
        self.assertEqual(actor.username, "actor")
        self.assertEqual(actor.first_name, "Ada")
        self.assertEqual(actor.last_name, "Lovelace")
        self.assertEqual(actor.profile_id, profile.id)
        self.assertEqual(actor.role, UserProfile.ROLE_LIBRARIAN)
        self.assertTrue(actor.must_change_password)
        self.assertEqual(actor.web_session_generation, 7)

    def test_new_request_loads_fresh_profile_facts(self):
        user = User.objects.create_user(username="fresh-actor", password="pw")
        first_request = RequestFactory().get("/")
        first_request.user = user
        first_actor = get_request_actor_context(first_request)

        UserProfile.objects.filter(user=user).update(
            role=UserProfile.ROLE_MANAGER,
            must_change_password=True,
            web_session_generation=3,
        )
        next_request = RequestFactory().get("/")
        next_request.user = user

        with self.assertNumQueries(1):
            next_actor = get_request_actor_context(next_request)

        self.assertEqual(first_actor.role, UserProfile.ROLE_READER)
        self.assertFalse(first_actor.must_change_password)
        self.assertEqual(first_actor.web_session_generation, 0)
        self.assertEqual(next_actor.profile_id, first_actor.profile_id)
        self.assertEqual(next_actor.role, UserProfile.ROLE_MANAGER)
        self.assertTrue(next_actor.must_change_password)
        self.assertEqual(next_actor.web_session_generation, 3)

    def test_anonymous_request_does_not_acquire_profile_facts(self):
        request = RequestFactory().get("/")
        request.user = AnonymousUser()

        with self.assertNumQueries(0):
            actor = get_request_actor_context(request)

        self.assertIsNone(actor)
