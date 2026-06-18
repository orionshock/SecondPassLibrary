from __future__ import annotations

import uuid

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
    # Legacy providerless field. Do not use for new external identity linking;
    # ExternalIdentity namespaces subjects by issuer and supports multiple links.
    external_subject_id = models.CharField(
        max_length=255, blank=True, null=True, unique=True
    )

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.get_username()} ({self.role})"

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


class ExternalIdentity(TimeStampedModel):
    """
    Future external-auth identity link.

    This model is infrastructure only. No login, callback, token, or claim
    processing currently reads from or writes to it.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="external_identities",
    )
    provider = models.CharField(max_length=100)
    issuer = models.URLField(max_length=500)
    subject = models.CharField(max_length=255)
    email_at_login = models.EmailField(blank=True)
    email_verified = models.BooleanField(default=False)
    selected_claims = models.JSONField(default=dict, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["issuer", "subject"],
                name="unique_external_identity_issuer_subject",
            )
        ]
        indexes = [
            models.Index(
                fields=["provider", "subject"],
                name="acct_ext_provider_subj_idx",
            )
        ]
        ordering = ["provider", "issuer", "subject"]

    def __str__(self):
        return f"{self.provider}: {self.subject}"


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


class ClientLoginRequest(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_DENIED = "denied"
    STATUS_CONSUMED = "consumed"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_DENIED, "Denied"),
        (STATUS_CONSUMED, "Consumed"),
        (STATUS_EXPIRED, "Expired"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_hash = models.CharField(max_length=64, db_index=True)
    client_name = models.CharField(max_length=200)
    client_type = models.CharField(max_length=64)
    status = models.CharField(
        max_length=16, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="approved_client_login_requests",
    )
    expires_at = models.DateTimeField()
    approved_at = models.DateTimeField(null=True, blank=True)
    consumed_at = models.DateTimeField(null=True, blank=True)

    request_user_agent = models.TextField(blank=True)
    request_ip = models.GenericIPAddressField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.client_name} ({self.client_type}) [{self.status}]"


class UserClientSession(TimeStampedModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_sessions",
    )
    name = models.CharField(max_length=200)
    client_type = models.CharField(max_length=64)
    token_hash = models.CharField(max_length=64, unique=True, db_index=True)

    last_seen_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        username = ""
        try:
            username = self.user.get_username()
        except Exception:
            username = ""
        return f"{username} ({self.name}) [{self.client_type}]"
