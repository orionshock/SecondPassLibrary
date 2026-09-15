from __future__ import annotations

from django.contrib.auth import get_user_model
from django.http import Http404
from django.test import TestCase
from rest_framework.exceptions import PermissionDenied, ValidationError

from accounts.models import UserProfile
from core.server_settings import (
    set_advanced_library_groups_enabled,
    set_server_setting,
)
from library.groups.api_access import (
    authorize_group_creation,
    authorize_group_deletion,
    authorize_group_metadata_mutation,
    authorize_membership_mutation,
    normal_book_assignment_group_or_404,
    normal_mutation_group_or_404,
)
from library.groups.book_assignment_workflows import (
    create_normal_book_assignment,
    remove_normal_book_assignment,
)
from library.groups.book_assignments import add_book_to_group
from library.groups.public_group import PUBLIC_GROUP_ID_SETTING
from library.models import Book, BookGroupAssignment, LibraryGroup, LibraryGroupMembership
from tests.library.helpers import set_user_role


class NormalGroupMutationAccessTests(TestCase):
    def setUp(self):
        set_advanced_library_groups_enabled(True)
        User = get_user_model()
        self.owner = User.objects.create_superuser(username="owner", password="pw")
        self.manager = User.objects.create_user(username="manager", password="pw")
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        self.curator = User.objects.create_user(username="curator", password="pw")
        self.reader = User.objects.create_user(username="reader", password="pw")
        self.target_manager = User.objects.create_user(
            username="target-manager", password="pw"
        )
        set_user_role(self.manager, UserProfile.ROLE_MANAGER)
        set_user_role(self.target_manager, UserProfile.ROLE_MANAGER)
        set_user_role(self.librarian, UserProfile.ROLE_LIBRARIAN)
        set_user_role(self.curator, UserProfile.ROLE_READER)
        set_user_role(self.reader, UserProfile.ROLE_READER)

        self.public = LibraryGroup.objects.create(name="Common Room")
        set_server_setting(
            key=PUBLIC_GROUP_ID_SETTING,
            value=str(self.public.id),
            description="Public/Common Room group id.",
        )
        self.club = LibraryGroup.objects.create(name="Club")
        self.other_group = LibraryGroup.objects.create(name="Other")
        LibraryGroupMembership.objects.create(
            user=self.curator, group=self.club, is_curator=True
        )
        LibraryGroupMembership.objects.create(user=self.curator, group=self.other_group)
        LibraryGroupMembership.objects.create(user=self.reader, group=self.club)

        self.club_book = Book.objects.create(title="Club Book")
        self.other_book = Book.objects.create(title="Other Book")
        self.hidden_book = Book.objects.create(title="Hidden Book")
        BookGroupAssignment.objects.create(book=self.club_book, group=self.club)
        BookGroupAssignment.objects.create(book=self.other_book, group=self.other_group)

    def test_metadata_role_matrix_keeps_field_specific_authority(self):
        cases = (
            (self.owner, True, True, None),
            (self.manager, True, True, None),
            (self.librarian, False, True, None),
            (self.librarian, True, False, PermissionDenied),
            (self.curator, False, True, None),
            (self.curator, True, False, PermissionDenied),
            (self.reader, False, True, PermissionDenied),
        )

        for actor, changes_name, changes_description, expected_error in cases:
            with self.subTest(
                actor=actor.username,
                changes_name=changes_name,
                changes_description=changes_description,
            ):
                access = authorize_group_metadata_mutation(
                    actor=actor, group=self.club
                )
                if expected_error is None:
                    access.authorize_patch(
                        changes_name=changes_name,
                        changes_description=changes_description,
                    )
                else:
                    with self.assertRaises(expected_error):
                        access.authorize_patch(
                            changes_name=changes_name,
                            changes_description=changes_description,
                        )

    def test_creation_membership_and_deletion_role_matrix(self):
        for actor, expected_error in (
            (self.owner, None),
            (self.manager, None),
            (self.librarian, PermissionDenied),
            (self.reader, PermissionDenied),
        ):
            with self.subTest(operation="create", actor=actor.username):
                if expected_error is None:
                    authorize_group_creation(actor=actor)
                else:
                    with self.assertRaises(expected_error):
                        authorize_group_creation(actor=actor)

            with self.subTest(operation="membership", actor=actor.username):
                if expected_error is None:
                    access = authorize_membership_mutation(
                        actor=actor, group=self.club
                    )
                    self.assertEqual(
                        access.target_user_or_404(
                            profile_id=self.target_manager.profile.id
                        ),
                        self.target_manager,
                    )
                else:
                    with self.assertRaises(expected_error):
                        authorize_membership_mutation(actor=actor, group=self.club)

            with self.subTest(operation="delete", actor=actor.username):
                if expected_error is None:
                    authorize_group_deletion(actor=actor, group=self.club)
                else:
                    with self.assertRaises(expected_error):
                        authorize_group_deletion(actor=actor, group=self.club)

    def test_book_assignment_uses_strict_visibility_and_exact_curatorship(self):
        assignment = create_normal_book_assignment(
            actor=self.curator,
            group_id=self.club.id,
            book_id=self.other_book.id,
        )
        self.assertEqual(assignment.book, self.other_book)
        self.assertEqual(assignment.group, self.club)
        with self.assertRaises(PermissionDenied):
            create_normal_book_assignment(
                actor=self.reader,
                group_id=self.club.id,
                book_id=self.club_book.id,
            )
        self.assertTrue(
            remove_normal_book_assignment(
                actor=self.curator,
                group_id=self.club.id,
                book_id=self.club_book.id,
            )
        )
        with self.assertRaises(Http404):
            create_normal_book_assignment(
                actor=self.curator,
                group_id=self.club.id,
                book_id=self.hidden_book.id,
            )

        for actor in (self.librarian, self.manager, self.owner):
            with self.subTest(actor=actor.username):
                assignment = create_normal_book_assignment(
                    actor=actor,
                    group_id=self.club.id,
                    book_id=self.hidden_book.id,
                )
                self.assertEqual(assignment.book, self.hidden_book)

    def test_group_and_book_anti_enumeration_converges_on_not_found(self):
        for group_id in (self.other_group.id, "00000000-0000-0000-0000-000000000001"):
            with self.subTest(group_id=group_id):
                with self.assertRaises(Http404):
                    normal_mutation_group_or_404(actor=self.reader, group_id=group_id)

        for book_id in (self.hidden_book.id, "00000000-0000-0000-0000-000000000001"):
            with self.subTest(book_id=book_id):
                with self.assertRaises(Http404):
                    create_normal_book_assignment(
                        actor=self.curator,
                        group_id=self.club.id,
                        book_id=book_id,
                    )

    def test_public_and_simple_mode_matrix_preserves_special_cases(self):
        for actor in (self.owner, self.manager, self.librarian, self.curator):
            with self.subTest(operation="public-metadata", actor=actor.username):
                with self.assertRaises(PermissionDenied):
                    authorize_group_metadata_mutation(actor=actor, group=self.public)

        with self.assertRaises(ValidationError):
            authorize_group_deletion(actor=self.manager, group=self.public)
        authorize_membership_mutation(actor=self.manager, group=self.public)
        normal_book_assignment_group_or_404(
            actor=self.librarian,
            group_id=self.public.id,
        )

        set_advanced_library_groups_enabled(False)
        for operation in (
            lambda: authorize_group_metadata_mutation(
                actor=self.owner, group=self.club
            ),
            lambda: authorize_group_deletion(actor=self.owner, group=self.club),
            lambda: authorize_membership_mutation(actor=self.owner, group=self.club),
            lambda: normal_book_assignment_group_or_404(
                actor=self.owner,
                group_id=self.club.id,
            ),
        ):
            with self.subTest(operation=operation):
                with self.assertRaises(Http404):
                    operation()

        authorize_membership_mutation(actor=self.manager, group=self.public)
        normal_book_assignment_group_or_404(
            actor=self.librarian,
            group_id=self.public.id,
        )

    def test_low_level_assignment_service_remains_independent_of_http_mode(self):
        set_advanced_library_groups_enabled(False)

        assignment = add_book_to_group(
            book=self.hidden_book,
            group=self.club,
            actor=self.owner,
        )

        self.assertEqual(assignment.book, self.hidden_book)
        self.assertEqual(assignment.group, self.club)
