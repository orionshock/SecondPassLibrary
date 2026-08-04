from __future__ import annotations

from django.http import Http404
from django.shortcuts import get_object_or_404
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError

from library.models import LibraryGroup
from library.queries import group_is_visible_to_user


def exclude_books_assigned_to_group(queryset, *, user, raw_group_id: str):
    raw_group_id = (raw_group_id or "").strip()
    if not raw_group_id:
        return queryset
    pk_field = LibraryGroup._meta.pk
    assert pk_field is not None
    try:
        group_id = pk_field.to_python(raw_group_id)
    except (ValueError, DjangoValidationError) as exc:
        raise ValidationError({"exclude_group": "Invalid id."}) from exc
    group = get_object_or_404(
        LibraryGroup.objects.all(),
        pk=group_id,
    )
    if not group_is_visible_to_user(user=user, group=group):
        raise Http404
    return queryset.exclude(group_assignments__group=group)
