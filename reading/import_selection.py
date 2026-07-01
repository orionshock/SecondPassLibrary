from __future__ import annotations

import json
from typing import Any

from .import_services import MarginaliaImportError


def parse_import_selection(*, raw_selection: object, plan: dict[str, Any]) -> dict[str, dict[str, dict[str, str]]] | None:
    if raw_selection in (None, ""):
        return None
    if not isinstance(raw_selection, str):
        raise _selection_error("selection must be a JSON string.")
    try:
        payload = json.loads(raw_selection)
    except json.JSONDecodeError as exc:
        raise _selection_error(f"selection must be valid JSON: {exc.msg}") from None
    if not isinstance(payload, dict) or not isinstance(payload.get("books"), list):
        raise _selection_error("selection must be an object with a books array.")

    plan_books = _plan_books(plan)
    selected: dict[str, dict[str, dict[str, str]]] = {}
    for book_index, raw_book in enumerate(payload["books"]):
        if not isinstance(raw_book, dict):
            raise _selection_error(f"selection.books[{book_index}] must be an object.")
        key = _book_key(raw_book, book_index)
        planned_book = plan_books.get(key)
        if planned_book is None:
            raise _selection_error(f"selected book {key!r} does not exist in the export.")
        raw_sessions = raw_book.get("sessions")
        if not isinstance(raw_sessions, list):
            raise _selection_error(f"selection.books[{book_index}].sessions must be an array.")

        sessions = selected.setdefault(key, {})
        valid_session_ids = {
            str(session.get("export_session_id") or "")
            for session in planned_book["summary"].get("sessions") or []
            if session.get("will_import")
        }
        for session_index, raw_session in enumerate(raw_sessions):
            if not isinstance(raw_session, dict):
                raise _selection_error(
                    f"selection.books[{book_index}].sessions[{session_index}] must be an object."
                )
            if raw_session.get("selected") is not True:
                continue
            session_id = str(raw_session.get("export_session_id") or "")
            if session_id not in valid_session_ids:
                raise _selection_error(
                    f"selected session {session_id!r} is not importable by the server."
                )
            if planned_book["local_book"] is None:
                raise _selection_error(f"selected book {key!r} is not matched to a visible local book.")
            sessions[session_id] = _session_overrides(raw_session)

    selected = {book: sessions for book, sessions in selected.items() if sessions}
    if not selected:
        raise _selection_error("selection must include at least one selected session.")
    return selected


def plan_book_key(*, exported_book: dict[str, Any], index: int) -> str:
    source = str(exported_book.get("source") or "").strip()
    if source:
        return source
    file_hash = str(exported_book.get("file_hash") or "").strip()
    if file_hash:
        return file_hash
    return f"title:{index}:{str(exported_book.get('title') or '').strip()}"


def _plan_books(plan: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        plan_book_key(exported_book=book["exported"], index=index): book
        for index, book in enumerate(plan.get("book_plans") or [])
    }


def _book_key(raw_book: dict[str, Any], index: int) -> str:
    source = str(raw_book.get("source") or "").strip()
    if source:
        return source
    file_hash = str(raw_book.get("file_hash") or "").strip()
    if file_hash:
        return file_hash
    return f"title:{index}:{str(raw_book.get('title') or '').strip()}"


def _session_overrides(raw_session: dict[str, Any]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if "name" in raw_session:
        overrides["name"] = str(raw_session.get("name") or "").strip()
    if "notes" in raw_session:
        overrides["notes"] = str(raw_session.get("notes") or "").strip()
    return overrides


def _selection_error(message: str) -> MarginaliaImportError:
    return MarginaliaImportError(
        "Import selection is invalid.",
        [{"path": "$.selection", "message": message}],
    )
