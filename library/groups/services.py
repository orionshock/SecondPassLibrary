from __future__ import annotations

from django.core.exceptions import ImproperlyConfigured


def configure_public_group(*, name: str, description: str = ""):
    raise ImproperlyConfigured("LibraryReWrite2607 group services are not rebuilt yet.")


def ensure_user_public_membership(*, user):
    raise ImproperlyConfigured("LibraryReWrite2607 group services are not rebuilt yet.")


def ensure_user_has_at_least_one_group(*, user) -> None:
    raise ImproperlyConfigured("LibraryReWrite2607 group services are not rebuilt yet.")


def ensure_book_public_assignment(*, book, added_by=None):
    raise ImproperlyConfigured("LibraryReWrite2607 group services are not rebuilt yet.")


def ensure_book_has_at_least_one_group(*, book, added_by=None) -> None:
    raise ImproperlyConfigured("LibraryReWrite2607 group services are not rebuilt yet.")


def bootstrap_public_group_membership_and_assignments() -> None:
    raise ImproperlyConfigured("LibraryReWrite2607 group services are not rebuilt yet.")
