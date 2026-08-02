from __future__ import annotations

from typing import Any

from django.core.exceptions import PermissionDenied, ValidationError

from .models import Shelf
from .policies import can_create_shelf, can_edit_shelf


def create_shelf(
    actor,
    *,
    name: str,
    description: str = "",
    owner_type: str,
    owner_user=None,
    owner_group=None,
    visibility: str = Shelf.VISIBILITY_PRIVATE,
) -> Shelf:
    if owner_type == Shelf.OWNER_TYPE_USER:
        owner_user = owner_user or actor

    if not can_create_shelf(
        user=actor,
        owner_type=owner_type,
        owner_user=owner_user,
        owner_group=owner_group,
    ):
        raise PermissionDenied("Not allowed.")

    shelf = Shelf(
        name=name,
        description=description,
        owner_type=owner_type,
        owner_user=owner_user,
        owner_group=owner_group,
        visibility=visibility,
        created_by=actor,
    )

    shelf.save()
    return shelf


def update_shelf(actor, shelf: Shelf, **fields: Any) -> Shelf:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")

    # Owner fields are immutable after creation.
    forbidden = {"owner_type", "owner_user", "owner_user_id", "owner_group", "owner_group_id", "created_by", "created_by_id"}
    if forbidden.intersection(fields.keys()):
        raise ValidationError("Shelf owner fields cannot be changed.")

    allowed = {"name", "description", "visibility"}
    for k in list(fields.keys()):
        if k not in allowed:
            raise ValidationError(f"Unsupported field: {k}")

    for k, v in fields.items():
        setattr(shelf, k, v)
    shelf.save()
    return shelf


def delete_shelf(actor, shelf: Shelf) -> None:
    if not can_edit_shelf(user=actor, shelf=shelf):
        raise PermissionDenied("Not allowed.")
    shelf.delete()
