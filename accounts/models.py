from django.conf import settings
from django.db import models

from core.models import TimeStampedModel


class UserProfile(TimeStampedModel):
    ROLE_MANAGER = "manager"
    ROLE_LIBRARIAN = "librarian"
    ROLE_READER = "reader"

    ROLE_CHOICES = [
        (ROLE_MANAGER, "Manager"),
        (ROLE_LIBRARIAN, "Librarian"),
        (ROLE_READER, "Reader"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(max_length=16, choices=ROLE_CHOICES, default=ROLE_READER)
    must_change_password = models.BooleanField(default=False)
    external_subject_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"

    @property
    def is_app_admin(self):
        # Compatibility alias: "app admin" means Manager in-app (Owner is is_superuser).
        return self.role == self.ROLE_MANAGER

    @property
    def is_manager(self):
        return self.role == self.ROLE_MANAGER

    @property
    def is_librarian(self):
        return self.role == self.ROLE_LIBRARIAN

    @property
    def is_reader(self):
        return self.role == self.ROLE_READER

    @property
    def is_regular_user(self):
        return self.is_reader


class UserWebSession(TimeStampedModel):
    """
    Companion tracking row for a Django web (browser/product UI) session.

    Notes:
    - This does not replace Django's session authentication. It is tracking only.
    - Revocation still deletes Django `django_session` rows; this model mirrors/tracks them.
    - `updated_at` acts as a "last_seen" timestamp for now (updated by middleware).
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="web_sessions",
    )
    session_key = models.CharField(max_length=128, unique=True, db_index=True)
    user_agent = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        username = ""
        try:
            username = self.user.get_username()
        except Exception:
            username = ""
        return f"{username} ({self.session_key})"
