from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q

from core.models import TimeStampedModel
from library.models import Book, LibraryGroup


class Shelf(TimeStampedModel):
    OWNER_TYPE_USER = "user"
    OWNER_TYPE_GROUP = "group"

    OWNER_TYPE_CHOICES = [
        (OWNER_TYPE_USER, "User"),
        (OWNER_TYPE_GROUP, "Group"),
    ]

    VISIBILITY_PRIVATE = "private"
    VISIBILITY_LISTED = "listed"

    VISIBILITY_CHOICES = [
        (VISIBILITY_PRIVATE, "Private"),
        (VISIBILITY_LISTED, "Listed"),
    ]

    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)

    owner_type = models.CharField(max_length=16, choices=OWNER_TYPE_CHOICES)
    owner_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="shelves_owned",
    )
    owner_group = models.ForeignKey(
        LibraryGroup,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="shelves_owned",
    )

    # Meaningful only for user-owned shelves. Group shelves must be private.
    visibility = models.CharField(
        max_length=16, choices=VISIBILITY_CHOICES, default=VISIBILITY_PRIVATE
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shelves_created",
    )

    class Meta:
        ordering = ["name", "created_at"]
        constraints = [
            models.CheckConstraint(
                name="shelf_exactly_one_owner",
                condition=Q(
                    owner_type="user",
                    owner_user__isnull=False,
                    owner_group__isnull=True,
                )
                | Q(
                    owner_type="group",
                    owner_group__isnull=False,
                    owner_user__isnull=True,
                ),
            ),
        ]

    def clean(self):
        super().clean()

        if self.owner_type == self.OWNER_TYPE_USER:
            if self.owner_user is None or self.owner_group is not None:
                raise ValidationError(
                    "User-owned shelf must have owner_user set and owner_group unset."
                )
        elif self.owner_type == self.OWNER_TYPE_GROUP:
            if self.owner_group is None or self.owner_user is not None:
                raise ValidationError(
                    "Group-owned shelf must have owner_group set and owner_user unset."
                )
            # Implementation choice: group shelves do not have discoverability state.
            # Enforce a single stable value in storage.
            if self.visibility != self.VISIBILITY_PRIVATE:
                raise ValidationError(
                    {"visibility": "Group-owned shelves must use visibility=private."}
                )
        else:
            raise ValidationError({"owner_type": "Invalid owner_type."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.name


class ShelfItem(TimeStampedModel):
    shelf = models.ForeignKey(Shelf, on_delete=models.CASCADE, related_name="items")
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name="shelf_items")
    position = models.IntegerField(default=0)
    added_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="shelf_items_added",
    )

    class Meta:
        ordering = ["position", "created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["shelf", "book"],
                name="unique_shelf_item_shelf_book",
            )
        ]

    def __str__(self) -> str:
        return f"{self.shelf.name}: {self.book.title}"
