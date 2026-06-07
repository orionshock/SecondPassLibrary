from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .import_services import plan_marginalia_import
from .import_selection import parse_import_selection, plan_book_key
from .models import Annotation, ReadingSession, SELECTOR_KIND_EPUB_CFI
from .profile import CURRENT_READING_PROFILE_VERSION


def apply_marginalia_import(*, user, payload: dict[str, Any], selection_raw: object = None) -> dict[str, Any]:
    plan = plan_marginalia_import(user=user, payload=payload)
    selection = parse_import_selection(raw_selection=selection_raw, plan=plan)
    result = _empty_result()

    with transaction.atomic():
        for book_index, planned_book in enumerate(plan["book_plans"]):
            exported_book = planned_book["exported"]
            local_book = planned_book["local_book"]
            preview = planned_book["summary"]
            book_key = plan_book_key(exported_book=exported_book, index=book_index)
            selected_sessions = None if selection is None else selection.get(book_key)
            if selection is not None and not selected_sessions:
                continue
            book_result = {
                "title": preview["title"],
                "match": preview["match"],
                "sessions_created": 0,
                "annotations_created": 0,
                "skipped": local_book is None,
            }
            result["books"].append(book_result)

            if local_book is None:
                result["summary"]["books_skipped"] += 1
                result["warnings"].append(
                    f"No visible local book matched '{book_result['title']}'. It was skipped."
                )
                continue

            result["summary"]["books_matched"] += 1
            for exported_session in exported_book.get("sessions") or []:
                export_session_id = exported_session.get("export_session_id") or ""
                overrides = None
                if selected_sessions is not None:
                    overrides = selected_sessions.get(export_session_id)
                    if overrides is None:
                        continue
                session = _create_historical_session(
                    user=user,
                    book=local_book,
                    exported_session=exported_session,
                    overrides=overrides or {},
                )
                book_result["sessions_created"] += 1
                result["summary"]["sessions_created"] += 1

                for exported_annotation in exported_session.get("annotations") or []:
                    if exported_annotation.get("is_deleted"):
                        continue
                    annotation = _create_annotation(
                        session=session,
                        exported_annotation=exported_annotation,
                        export_session_id=export_session_id,
                    )
                    if annotation is None:
                        continue
                    book_result["annotations_created"] += 1
                    _count_annotation(result["summary"], annotation)

    return result


def _empty_result() -> dict[str, Any]:
    return {
        "applied": True,
        "summary": {
            "books_matched": 0,
            "books_skipped": 0,
            "sessions_created": 0,
            "annotations_created": 0,
            "bookmarks_created": 0,
            "highlights_created": 0,
            "commented_highlights_created": 0,
        },
        "books": [],
        "warnings": [],
    }


def _create_historical_session(
    *,
    user,
    book,
    exported_session: dict[str, Any],
    overrides: dict[str, str],
) -> ReadingSession:
    completed_at = _dt(exported_session.get("completed_at")) or _dt(
        exported_session.get("updated_at")
    ) or timezone.now()
    session = ReadingSession.objects.create(
        user=user,
        book=book,
        name=_session_text(overrides, exported_session, "name")[:255],
        notes=_session_text(overrides, exported_session, "notes"),
        status=ReadingSession.STATUS_COMPLETED,
        is_active=False,
        completed_at=completed_at,
    )
    started_at = _dt(exported_session.get("started_at"))
    if started_at is not None:
        session.started_at = started_at
        session.save(update_fields=["started_at", "updated_at"])
    return session


def _create_annotation(
    *,
    session: ReadingSession,
    exported_annotation: dict[str, Any],
    export_session_id: str,
) -> Annotation | None:
    compact = _annotation_compact(exported_annotation)
    if compact is None:
        return None
    annotation = Annotation.objects.create(
        session=session,
        book=session.book,
        book_file=getattr(session.book, "file", None),
        motivation=compact["motivation"],
        anchor_kind=compact["anchor_kind"],
        selector_kind=SELECTOR_KIND_EPUB_CFI,
        selector_value=compact["selector_value"],
        highlight_text=compact["highlight_text"],
        quote_prefix=compact["quote_prefix"],
        quote_suffix=compact["quote_suffix"],
        highlight_color=compact["highlight_color"],
        comment_text=compact["comment_text"],
        source_import={"format": "spl_native_marginalia", "export_session_id": export_session_id},
        profile_version=CURRENT_READING_PROFILE_VERSION,
    )
    created_at = _dt(exported_annotation.get("created_at"))
    updated_at = _dt(exported_annotation.get("updated_at"))
    update_fields = []
    if created_at is not None:
        annotation.created_at = created_at
        update_fields.append("created_at")
    if updated_at is not None:
        annotation.updated_at = updated_at
        update_fields.append("updated_at")
    if update_fields:
        annotation.save(update_fields=update_fields)
    return annotation


def _annotation_compact(exported_annotation: dict[str, Any]) -> dict[str, str] | None:
    motivations = set(exported_annotation.get("motivation") or [])
    selector = _selectors(exported_annotation.get("target") or {})
    fragment = next((item for item in selector if item.get("type") == "FragmentSelector"), {})
    quote = next((item for item in selector if item.get("type") == "TextQuoteSelector"), {})
    selector_value = fragment.get("value") or ""
    if not selector_value:
        return None

    describing = ""
    color = ""
    comment = ""
    for body in exported_annotation.get("body") or []:
        if body.get("purpose") == "describing" and not describing:
            describing = body.get("value") or ""
            color = body.get("color") or ""
        elif body.get("purpose") == "commenting" and not comment:
            comment = body.get("value") or ""

    if "highlighting" in motivations:
        return {
            "motivation": Annotation.MOTIVATION_HIGHLIGHTING,
            "anchor_kind": Annotation.ANCHOR_KIND_HIGHLIGHT,
            "selector_value": selector_value,
            "highlight_text": describing or quote.get("exact") or "",
            "quote_prefix": quote.get("prefix") or "",
            "quote_suffix": quote.get("suffix") or "",
            "highlight_color": color or "yellow",
            "comment_text": comment,
        }
    if "bookmarking" in motivations:
        return {
            "motivation": Annotation.MOTIVATION_BOOKMARKING,
            "anchor_kind": Annotation.ANCHOR_KIND_BOOKMARK,
            "selector_value": selector_value,
            "highlight_text": "",
            "quote_prefix": "",
            "quote_suffix": "",
            "highlight_color": "",
            "comment_text": "",
        }
    return None


def _selectors(target: dict[str, Any]) -> list[dict[str, Any]]:
    selector = target.get("selector")
    if isinstance(selector, list):
        return [item for item in selector if isinstance(item, dict)]
    if isinstance(selector, dict):
        return [selector]
    return []


def _count_annotation(summary: dict[str, int], annotation: Annotation) -> None:
    summary["annotations_created"] += 1
    if annotation.anchor_kind == Annotation.ANCHOR_KIND_BOOKMARK:
        summary["bookmarks_created"] += 1
        return
    summary["highlights_created"] += 1
    if annotation.comment_text:
        summary["commented_highlights_created"] += 1


def _dt(value: object):
    if not value:
        return None
    if not isinstance(value, str):
        return None
    return parse_datetime(value)


def _session_text(overrides: dict[str, str], exported_session: dict[str, Any], key: str) -> str:
    if key in overrides:
        return overrides[key].strip()
    return str(exported_session.get(key) or "").strip()
