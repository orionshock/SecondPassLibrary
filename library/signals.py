from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .group_services import ensure_user_public_membership, ensure_user_has_at_least_one_group, ensure_book_has_at_least_one_group
from .models import BookGroupAssignment, LibraryGroupMembership


User = get_user_model()


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
    ensure_user_has_at_least_one_group(user=instance.user)


@receiver(post_delete, sender=BookGroupAssignment)
def ensure_book_has_group_after_assignment_delete(sender, instance, **kwargs):
    """
    Safety invariant: a book should not remain without any group assignments.

    If the last assignment is removed, re-assign the book back to Public.
    """
    if instance.book_id is None:
        return
    ensure_book_has_at_least_one_group(book=instance.book, added_by=None)
