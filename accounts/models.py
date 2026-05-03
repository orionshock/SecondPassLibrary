from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    ROLE_ADMIN = 'admin'
    ROLE_USER = 'user'

    ROLE_CHOICES = [
        (ROLE_ADMIN, 'Admin'),
        (ROLE_USER, 'User'),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_USER)
    external_subject_id = models.CharField(max_length=255, blank=True, null=True, unique=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f'{self.user.get_username()} ({self.role})'
