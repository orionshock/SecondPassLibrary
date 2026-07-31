from __future__ import annotations

import json

from django.core.files.uploadedfile import SimpleUploadedFile

from marginalia.profile import MARGINALIA_PROFILE_URI


def archive_payload(*, file_hash: str, sessions: list[dict] | None = None) -> dict:
    return {
        "type": "SecondPassMarginaliaExport",
        "schemaVersion": "0.1.0",
        "profile": MARGINALIA_PROFILE_URI,
        "generatedAt": "2026-07-30T12:00:00Z",
        "generator": "Test Reader",
        "books": [
            {
                "fileHash": file_hash,
                "title": "Archive Book",
                "authors": ["Example Author"],
                "readingSessions": sessions or [archive_session()],
            }
        ],
    }


def archive_session(
    *,
    source_id: str = "source-session-1",
    name: str = "Second pass",
    status: str = "active",
    annotations: list[dict] | None = None,
) -> dict:
    return {
        "sourceReadingSessionId": source_id,
        "name": name,
        "notes": "Session notes",
        "status": status,
        "startedAt": "2026-07-01T12:00:00Z",
        "closedAt": None if status == "active" else "2026-07-20T12:00:00Z",
        "createdAt": "2026-07-01T12:00:00Z",
        "updatedAt": "2026-07-20T12:00:00Z",
        "progress": {
            "cfi": "  opaque::progress  ",
            "locationLabel": "  Chapter 08 · 42%  ",
            "updatedAt": "2026-07-19T12:00:00Z",
        },
        "annotations": [archive_highlight()] if annotations is None else annotations,
    }


def archive_highlight() -> dict:
    return {
        "clientAnnotationId": "highlight-1",
        "kind": "highlight",
        "location": {
            "cfi": "  opaque::highlight  ",
            "locationLabel": "  Chapter 08 · 42% · Context  ",
        },
        "body": {
            "text": "Selected passage",
            "prefix": "Before ",
            "suffix": " after.",
            "color": "yellow",
            "note": "Reader note",
        },
        "createdAt": "2026-07-18T12:00:00Z",
        "updatedAt": "2026-07-18T12:00:00Z",
    }


def archive_upload(payload: dict, *, name: str = "user supplied name.json"):
    return SimpleUploadedFile(
        name,
        json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        content_type="application/json",
    )
