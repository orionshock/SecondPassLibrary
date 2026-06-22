from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from django.db.models.signals import pre_delete
from django.dispatch import receiver
import threading

from core.models import ServerSetting

from .group_services import ensure_user_public_membership, ensure_user_has_at_least_one_group, ensure_book_has_at_least_one_group
from .group_services import PUBLIC_GROUP_ID_SETTING, get_public_group
from .models import Book, BookGroupAssignment, LibraryGroupMembership


User = get_user_model()


_state = threading.local()


def _deleting_book_ids() -> set[str]:
    ids = getattr(_state, "deleting_book_ids", None)
    if ids is None:
        ids = set()
        _state.deleting_book_ids = ids
    return ids


def _deleting_user_ids() -> set[str]:
    ids = getattr(_state, "deleting_user_ids", None)
    if ids is None:
        ids = set()
        _state.deleting_user_ids = ids
    return ids


@receiver(pre_delete, sender=User)
def _mark_user_deleting(sender, instance, **kwargs):
    user_id = getattr(instance, "id", None)
    if user_id is None:
        return
    _deleting_user_ids().add(str(user_id))


@receiver(post_delete, sender=User)
def _unmark_user_deleting(sender, instance, **kwargs):
    user_id = getattr(instance, "id", None)
    if user_id is None:
        return
    _deleting_user_ids().discard(str(user_id))


@receiver(pre_delete, sender=Book)
def _mark_book_deleting(sender, instance: Book, **kwargs):
    book_id = getattr(instance, "id", None)
    if book_id is None:
        return
    _deleting_book_ids().add(str(book_id))


@receiver(post_delete, sender=Book)
def _unmark_book_deleting(sender, instance: Book, **kwargs):
    book_id = getattr(instance, "id", None)
    if book_id is None:
        return
    _deleting_book_ids().discard(str(book_id))


@receiver(post_save, sender=User)
def ensure_public_group_membership(sender, instance, created, **kwargs):
    if created:
        ensure_user_public_membership(user=instance)


@receiver(post_delete, sender=LibraryGroupMembership)
def ensure_user_has_group_after_membership_delete(sender, instance, **kwargs):
    """
    Safety invariant: a user should not remain without any group memberships.

    If the last membership is removed (including Public), re-add Public as a fallback.
    """
    if instance.user_id is None:
        return
    if str(instance.user_id) in _deleting_user_ids():
        return
    ensure_user_has_at_least_one_group(user=instance.user)


@receiver(post_delete, sender=BookGroupAssignment)
def ensure_book_has_group_after_assignment_delete(sender, instance, **kwargs):
    """
    Safety invariant: a book should not remain without any group assignments.

    If the last assignment is removed, re-assign the book back to Public.
    """
    if instance.book_id is None:
        return

    # If the Book is being deleted, skip this safety repair. Otherwise, bulk
    # deletions (including Django admin delete actions) can re-create assignments
    # during cascade deletes and trigger FK constraint errors on commit.
    if str(instance.book_id) in _deleting_book_ids():
        return
    ensure_book_has_at_least_one_group(book=instance.book, added_by=None)


@receiver(post_save, sender=ServerSetting)
def repair_public_group_setting_on_save(sender, instance: ServerSetting, **kwargs):
    if instance.key != PUBLIC_GROUP_ID_SETTING:
        return
    # Canonical repair path. Safe even if already valid.
    get_public_group()


@receiver(post_delete, sender=ServerSetting)
def repair_public_group_setting_on_delete(sender, instance: ServerSetting, **kwargs):
    if instance.key != PUBLIC_GROUP_ID_SETTING:
        return
    get_public_group()
