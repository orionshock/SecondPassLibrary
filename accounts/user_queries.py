from __future__ import annotations

from typing import Any

from django.db.models import Case, IntegerField, Q, QuerySet, Value, When
from django.db.models.functions import Concat, Lower


def filter_and_order_managed_users(
    queryset: QuerySet,
    *,
    query: dict[str, Any],
) -> QuerySet:
    search = str(query.get("q") or "")
    if search:
        queryset = queryset.annotate(
            _display_name=Concat("first_name", Value(" "), "last_name")
        ).filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
            | Q(email__icontains=search)
            | Q(_display_name__icontains=search)
        )

    role = str(query.get("role") or "")
    if role == "owner":
        queryset = queryset.filter(is_superuser=True)
    elif role == "curator":
        queryset = queryset.filter(
            library_group_memberships__is_curator=True
        ).distinct()
    elif role:
        queryset = queryset.filter(is_superuser=False, profile__role=role)

    active = str(query.get("is_active") or "")
    if active:
        queryset = queryset.filter(is_active=active == "true")

    ordering = str(query.get("ordering") or "username") or "username"
    descending = ordering.startswith("-")
    key = ordering.removeprefix("-")
    if key == "name":
        terms = [Lower("last_name"), Lower("first_name"), Lower("username"), "id"]
    elif key == "role":
        queryset = queryset.annotate(
            _role_rank=Case(
                When(is_superuser=True, then=Value(0)),
                When(profile__role="manager", then=Value(1)),
                When(profile__role="librarian", then=Value(2)),
                default=Value(3),
                output_field=IntegerField(),
            )
        )
        terms = ["_role_rank", Lower("username"), "id"]
    elif key == "is_active":
        terms = ["is_active", Lower("username"), "id"]
    else:
        terms = [Lower("username"), "id"]

    ordered_terms = []
    for term in terms:
        if isinstance(term, str):
            ordered_terms.append(f"-{term}" if descending else term)
        else:
            ordered_terms.append(term.desc() if descending else term.asc())
    return queryset.order_by(*ordered_terms)
