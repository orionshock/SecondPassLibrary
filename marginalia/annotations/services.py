from __future__ import annotations

from collections.abc import Sequence

from django.db import transaction
from django.db.models import F

from library.queries import visible_books_for_user
from marginalia.exceptions import BookAccessRequiredError, SessionClosedError
from marginalia.models import Annotation, ReadingSession


@transaction.atomic
def synchronize_annotations(*, user, session_id, operations: Sequence[dict]) -> ReadingSession:
    session = ReadingSession.objects.select_for_update().get(
        pk=session_id,
        user=user,
    )
    if not session.is_active:
        raise SessionClosedError
    if not visible_books_for_user(user, cached=False).filter(
        pk=session.book_id
    ).exists():
        raise BookAccessRequiredError

    # SQLite has no row-level SELECT FOR UPDATE. This no-op compare-and-set
    # acquires its write lock and also prevents a stale write after close.
    active = ReadingSession.objects.filter(
        pk=session.pk,
        user=user,
        status=ReadingSession.STATUS_ACTIVE,
    ).update(updated_at=F("updated_at"))
    if not active:
        raise SessionClosedError

    client_ids = [_operation_client_id(operation) for operation in operations]
    existing = {
        annotation.client_id: annotation
        for annotation in Annotation.objects.select_for_update().filter(
            session=session,
            client_id__in=client_ids,
        )
    }

    for operation in operations:
        client_id = _operation_client_id(operation)
        annotation = existing.get(client_id)
        if operation["action"] == "delete":
            if annotation is not None and not annotation.is_deleted:
                annotation.is_deleted = True
                annotation.save(update_fields=["is_deleted", "updated_at"])
            continue

        values = _annotation_values(operation["annotation"])
        if annotation is None:
            annotation = Annotation.objects.create(
                session=session,
                client_id=client_id,
                **values,
            )
            existing[client_id] = annotation
            continue

        changed_fields = [
            field for field, value in values.items() if getattr(annotation, field) != value
        ]
        if annotation.is_deleted:
            annotation.is_deleted = False
            changed_fields.append("is_deleted")
        if not changed_fields:
            continue
        for field, value in values.items():
            setattr(annotation, field, value)
        annotation.save(update_fields=[*changed_fields, "updated_at"])

    return session


def _operation_client_id(operation: dict) -> str:
    if operation["action"] == "upsert":
        return operation["annotation"]["client_id"]
    return operation["client_id"]


def _annotation_values(annotation: dict) -> dict:
    location = annotation["location"]
    if annotation["kind"] == Annotation.KIND_BOOKMARK:
        return {
            "kind": Annotation.KIND_BOOKMARK,
            "cfi": location["cfi"],
            "location_label": location.get("location_label", ""),
            "highlight_text": "",
            "quote_prefix": "",
            "quote_suffix": "",
            "highlight_color": "",
            "comment_text": "",
            "is_deleted": False,
        }

    body = annotation["body"]
    return {
        "kind": Annotation.KIND_HIGHLIGHT,
        "cfi": location["cfi"],
        "location_label": location.get("location_label", ""),
        "highlight_text": body["text"],
        "quote_prefix": body.get("prefix", ""),
        "quote_suffix": body.get("suffix", ""),
        "highlight_color": body.get("color", "yellow"),
        "comment_text": body.get("note", ""),
        "is_deleted": False,
    }
