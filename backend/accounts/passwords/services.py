from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from accounts.local_passwords import generate_temporary_password, validate_new_password
from accounts.operational_logging import logger, user_log_label, user_uuid
from accounts.profiles import get_or_create_profile
from accounts.users.services import can_reset_user_password


@dataclass(frozen=True)
class ManagedPasswordResetResult:
    username: str
    temporary_password: str

    @property
    def copy_block(self) -> str:
        return f"Username: {self.username}\nPassword: {self.temporary_password}"

def change_current_user_password(
    *,
    user,
    current_password: str,
    new_password: str,
    confirm_password: str,
    current_session=None,
) -> None:
    if getattr(user, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    if not (current_password or ""):
        raise ValidationError({"current_password": "Current password is required."})

    if not user.check_password(current_password):
        raise ValidationError({"current_password": "Current password is incorrect."})

    if (new_password or "") != (confirm_password or ""):
        raise ValidationError({"confirm_password": "Passwords do not match."})

    validate_new_password(new_password=new_password, user=user)
    if (new_password or "") == (current_password or ""):
        raise ValidationError({"new_password": "New password must be different from current password."})

    profile = get_or_create_profile(user=user)
    forced_change = profile.must_change_password
    with transaction.atomic():
        user.set_password(new_password)
        user.full_clean()
        user.save(update_fields=["password"])

        if profile.must_change_password:
            profile.must_change_password = False
            profile.save(update_fields=["must_change_password", "updated_at"])

        from accounts import session_control

        session_control.user_changed_own_password(user, current_session)
        actor = user_uuid(user)
        transaction.on_commit(
            lambda: logger.info(
                "Self password changed: actor=%s target=%s forced=%s",
                actor,
                actor,
                forced_change,
            )
        )


def reset_managed_user_password(
    *,
    actor,
    target_user,
) -> ManagedPasswordResetResult:
    if getattr(actor, "is_anonymous", False):
        raise PermissionDenied("Not allowed.")

    if getattr(actor, "id", None) == getattr(target_user, "id", None):
        raise PermissionDenied("Cannot reset your own password here.")

    if not can_reset_user_password(actor=actor, target_user=target_user):
        raise PermissionDenied("Not allowed.")

    temporary_password = generate_temporary_password()

    with transaction.atomic():
        target_user.set_password(temporary_password)
        target_user.full_clean()
        target_user.save(update_fields=["password"])

        apply_managed_password_change_lifecycle(target_user=target_user, actor=actor)
        actor_label = user_log_label(actor)
        target_label = user_log_label(target_user)
        transaction.on_commit(
            lambda: logger.info(
                "Managed password reset completed: actor=%s target=%s",
                actor_label,
                target_label,
            )
        )
    return ManagedPasswordResetResult(
        username=target_user.get_username(),
        temporary_password=temporary_password,
    )


def apply_managed_password_change_lifecycle(*, target_user, actor=None) -> None:
    profile = get_or_create_profile(user=target_user)
    must_change_password = target_user.has_usable_password()
    if profile.must_change_password is not must_change_password:
        profile.must_change_password = must_change_password
        profile.full_clean()
        profile.save(update_fields=["must_change_password", "updated_at"])

    from accounts import session_control

    session_control.admin_reset_user_password(target_user, actor=actor)
