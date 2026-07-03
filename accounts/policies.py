from __future__ import annotations

from django.contrib.auth.models import AnonymousUser

from .models import UserProfile


def is_owner(user) -> bool:
    return bool(getattr(user, "is_superuser", False))


def _get_profile(user) -> UserProfile | None:
    if user is None or isinstance(user, AnonymousUser) or getattr(user, "is_anonymous", False):
        return None
    try:
        return UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return None


def _profile_role(user) -> str | None:
    profile = _get_profile(user)
    return profile.role if profile is not None else None


def _is_manager_role(user) -> bool:
    return _profile_role(user) == UserProfile.ROLE_MANAGER


def _is_librarian_role(user) -> bool:
    return _profile_role(user) == UserProfile.ROLE_LIBRARIAN


def is_manager(user) -> bool:
    if is_owner(user):
        return True
    return _is_manager_role(user)


def is_librarian(user) -> bool:
    if is_owner(user):
        return True
    return _is_librarian_role(user)


def is_reader(user) -> bool:
    if user is None or getattr(user, "is_anonymous", False):
        return False
    if is_owner(user) or is_manager(user) or is_librarian(user):
        return True
    profile = _get_profile(user)
    # Missing profile should behave like reader for now.
    return bool(profile is None or profile.role == UserProfile.ROLE_READER)


def can_manage_users(user) -> bool:
    return is_owner(user) or is_manager(user)


def can_create_user_with_role(*, actor, role: str) -> bool:
    """
    Permission check for creating a new user with a given global role.

    Notes:
    - Uses the same high-level role rules as can_assign_global_role, but since a
      target user does not exist yet, the check is based on the actor + desired role.
    """
    if role not in {UserProfile.ROLE_MANAGER, UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}:
        return False

    if is_owner(actor):
        return True

    if not _is_manager_role(actor):
        return False

    # Only Owner can create Managers.
    if role == UserProfile.ROLE_MANAGER:
        return False

    return True


def can_assign_global_role(*, actor, target_user, new_role: str) -> bool:
    if new_role not in {UserProfile.ROLE_MANAGER, UserProfile.ROLE_LIBRARIAN, UserProfile.ROLE_READER}:
        return False

    if is_owner(actor):
        return True

    if not _is_manager_role(actor):
        return False

    # Managers cannot edit Owner accounts.
    if is_owner(target_user):
        return False

    # Only Owner can promote to Manager.
    if new_role == UserProfile.ROLE_MANAGER:
        return False

    # Only Owner can demote existing Managers.
    if _is_manager_role(target_user):
        return False

    return True


def can_manage_user(*, actor, target_user) -> bool:
    if is_owner(actor):
        return True

    if not _is_manager_role(actor):
        return False

    if is_owner(target_user):
        return False

    # Managers cannot manage other Managers.
    if _is_manager_role(target_user):
        return False

    return True


def can_reset_user_password(*, actor, target_user) -> bool:
    """
    Password reset via managed endpoint (not self-service).

    Rules:
    - Managers can reset Librarian/Reader only (never Owner/Manager).
    - Owners can reset Manager/Librarian/Reader (never self via managed reset).
    """
    if getattr(actor, "is_anonymous", False):
        return False
    if getattr(actor, "id", None) == getattr(target_user, "id", None):
        return False
    if is_owner(actor):
        return True
    return can_manage_user(actor=actor, target_user=target_user)
