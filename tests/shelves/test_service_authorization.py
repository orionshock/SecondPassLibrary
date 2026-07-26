from __future__ import annotations

from django.core.exceptions import PermissionDenied
from django.test import TestCase

from shelves.models import Shelf
from shelves.policies import can_create_shelf
from shelves.services import create_shelf
from tests.shelves.service_helpers import ShelfServiceFixtureMixin


class ShelfServiceAuthorizationTests(ShelfServiceFixtureMixin, TestCase):
    def test_user_cannot_create_shelf_for_other_user(self):
        with self.assertRaises(PermissionDenied):
            create_shelf(
                self.reader,
                name="S",
                owner_type=Shelf.OWNER_TYPE_USER,
                owner_user=self.other,
            )

    def test_group_shelf_create_policy_is_group_specific(self):
        self.assertTrue(
            can_create_shelf(
                user=self.curator,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=self.curated_group,
            )
        )
        self.assertFalse(
            can_create_shelf(
                user=self.curator,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=self.group,
            )
        )
        self.assertFalse(
            can_create_shelf(
                user=self.curator,
                owner_type=Shelf.OWNER_TYPE_GROUP,
                owner_group=self.public,
            )
        )
