from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase
from rest_framework import status

from .models import UserProfile


class UserProfileModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')

    def test_user_profile_creation(self):
        profile = UserProfile.objects.create(user=self.user, role=UserProfile.ROLE_USER)
        self.assertEqual(profile.user, self.user)
        self.assertEqual(profile.role, UserProfile.ROLE_USER)
        self.assertIsNone(profile.external_subject_id)

    def test_user_profile_str(self):
        profile = UserProfile.objects.create(user=self.user, role=UserProfile.ROLE_ADMIN)
        self.assertEqual(str(profile), 'testuser (admin)')


class UserProfileAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.client.login(username='testuser', password='testpass')

    def test_authenticated_access(self):
        response = self.client.get('/api/v1/accounts/profiles/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
