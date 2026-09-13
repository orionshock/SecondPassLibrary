from __future__ import annotations

from dataclasses import dataclass

from django.http import Http404
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import UserProfile
from accounts.roles import is_librarian, is_manager
from core.server_settings import advanced_library_groups_enabled
from library.groups.public_group import is_public_group
from library.models import Book, LibraryGroup, LibraryGroupMembership
from library.queries import group_is_visible_to_user, visible_books_for_user
from library.roles import is_curator


def normal_mutation_group_or_404(*, actor, group_id) -> LibraryGroup:
    """Resolve a Group without exposing Groups hidden from the HTTP actor."""
    group = LibraryGroup.objects.filter(pk=group_id).first()
    if group is None or not group_is_visible_to_user(user=actor, group=group):
        raise Http404
    return group


def authorize_group_creation(*, actor) -> None:
    if not advanced_library_groups_enabled():
        raise Http404
    if not is_manager(actor):
        raise PermissionDenied("Not allowed to create library groups.")


@dataclass(frozen=True)
class MetadataMutationAccess:
    actor: object
    group: LibraryGroup

    def authorize_patch(
        self, *, changes_name: bool, changes_description: bool
    ) -> None:
        if changes_name and not is_manager(self.actor):
            raise PermissionDenied("Not allowed to rename this library group.")
        if changes_description and not is_curator(self.actor, self.group):
            raise PermissionDenied(
                "Not allowed to update this library group description."
            )


def authorize_group_metadata_mutation(
    *, actor, group: LibraryGroup
) -> MetadataMutationAccess:
    _require_group_mutation_mode(group)
    if is_public_group(group):
        raise PermissionDenied(
            "Public group identity is managed through Server Settings."
        )
    return MetadataMutationAccess(actor=actor, group=group)


def authorize_group_deletion(*, actor, group: LibraryGroup) -> None:
    _require_group_mutation_mode(group)
    if is_public_group(group):
        raise ValidationError("Public/Common Room group cannot be deleted.")
    if not is_manager(actor):
        raise PermissionDenied("Not allowed to delete this library group.")


@dataclass(frozen=True)
class MembershipMutationAccess:
    group: LibraryGroup

    def target_user_or_404(self, *, profile_id):
        try:
            return UserProfile.objects.select_related("user").get(pk=profile_id).user
        except UserProfile.DoesNotExist as exc:
            raise Http404 from exc

    def membership_for_update(self, *, profile_id) -> LibraryGroupMembership:
        user = self.target_user_or_404(profile_id=profile_id)
        membership = (
            LibraryGroupMembership.objects.filter(group=self.group, user=user)
            .select_related("user", "user__profile", "group")
            .first()
        )
        if membership is None:
            raise Http404
        return membership


def authorize_membership_mutation(
    *, actor, group: LibraryGroup
) -> MembershipMutationAccess:
    _require_group_mutation_mode(group)
    if not is_manager(actor):
        raise PermissionDenied("Not allowed to manage group memberships.")
    return MembershipMutationAccess(group=group)


@dataclass(frozen=True)
class BookAssignmentMutationAccess:
    actor: object
    group: LibraryGroup

    def book_for_add(self, *, book_id) -> Book:
        book = self._visible_book_or_404(book_id)
        if not is_librarian(self.actor) and not is_curator(self.actor, self.group):
            raise PermissionDenied("Not allowed to add books to this group.")
        return book

    def book_for_removal(self, *, book_id) -> Book:
        book = self._visible_book_or_404(book_id)
        if not is_curator(self.actor, self.group):
            raise PermissionDenied("Not allowed to remove books from this group.")
        return book

    def _visible_book_or_404(self, book_id) -> Book:
        try:
            book = Book.objects.get(pk=book_id)
        except Book.DoesNotExist as exc:
            raise Http404 from exc
        if is_librarian(self.actor):
            return book
        if not visible_books_for_user(self.actor, cached=False).filter(pk=book.pk).exists():
            raise Http404
        return book


def authorize_book_assignment_mutation(
    *, actor, group: LibraryGroup
) -> BookAssignmentMutationAccess:
    _require_group_mutation_mode(group)
    return BookAssignmentMutationAccess(actor=actor, group=group)


def _require_group_mutation_mode(group: LibraryGroup) -> None:
    """Reject custom-Group management in Simple Mode without hiding Group reads."""
    if not advanced_library_groups_enabled() and not is_public_group(group):
        raise Http404
