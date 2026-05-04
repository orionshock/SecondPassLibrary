from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from .models import UserProfile


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_user_creation_creates_profile(self):
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())
        profile = self.user.profile
        self.assertEqual(profile.role, UserProfile.ROLE_USER)
        self.assertIsNone(profile.external_subject_id)

    def test_user_profile_role_helpers(self):
        profile = self.user.profile
        self.assertTrue(profile.is_regular_user)
        self.assertFalse(profile.is_app_admin)
        profile.role = UserProfile.ROLE_ADMIN
        profile.save()
        profile.refresh_from_db()
        self.assertTrue(profile.is_app_admin)
        self.assertFalse(profile.is_regular_user)

    def test_user_profile_str(self):
        profile = self.user.profile
        self.assertEqual(str(profile), 'testuser (user)')
        profile.role = UserProfile.ROLE_ADMIN
        profile.save()
        profile.refresh_from_db()
        self.assertEqual(str(profile), 'testuser (admin)')


class UserProfileAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass', email='test@example.com')
        self.client.login(username='testuser', password='testpass')

    def test_authenticated_access(self):
        response = self.client.get('/api/v1/accounts/profiles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_me(self):
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'testuser')
        self.assertEqual(response.data['email'], 'test@example.com')
        self.assertEqual(response.data['role'], UserProfile.ROLE_USER)
        self.assertIn('profile_id', response.data)

    def test_anonymous_cannot_access_me(self):
        self.client.logout()
        response = self.client.get('/api/v1/accounts/me/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
