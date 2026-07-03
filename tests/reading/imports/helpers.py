from __future__ import annotations

import json
from typing import Any

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile

from reading.import_staging import stage_marginalia_import
from tests.utils.books import create_file_backed_book


User = get_user_model()


class MarginaliaImportFixtureMixin:
    def set_up_import_books(self) -> None:
        self.user = User.objects.create_user(username="reader", password="pw")
        self.visible = create_file_backed_book(
            title="Visible Match",
            epub_bytes=b"visible-match",
        ).book
        self.visible.authors.create(name="Author One")
        self.hidden = create_file_backed_book(
            title="Hidden Match",
            epub_bytes=b"hidden-match",
            assign_public=False,
        ).book

    def upload_payload(self, payload: Any) -> SimpleUploadedFile:
        if isinstance(payload, bytes):
            content = payload
        else:
            content = json.dumps(payload).encode("utf-8")
        return SimpleUploadedFile("marginalia.json", content, content_type="application/json")

    def post_preview_payload(self, payload: Any):
        return self.client.post(
            "/api/v1/reading/import/preview/",
            {"file": self.upload_payload(payload)},
            format="multipart",
        )

    def post_apply_payload(self, payload: Any, *, selection: Any = None):
        data: dict[str, Any] = {"file": self.upload_payload(payload)}
        if selection is not None:
            data["selection"] = selection if isinstance(selection, str) else json.dumps(selection)
        return self.client.post("/api/v1/reading/import/apply/", data, format="multipart")

    def post_apply_staged_payload(self, payload: dict[str, Any], *, selection: Any = None):
        return self.post_apply_token(
            stage_marginalia_import(user=self.user, payload=payload),
            selection=selection,
        )

    def post_apply_token(self, token: str, *, selection: Any = None):
        data: dict[str, Any] = {"import_token": token}
        if selection is not None:
            data["selection"] = selection if isinstance(selection, str) else json.dumps(selection)
        return self.client.post("/api/v1/reading/import/apply/", data, format="multipart")

    def preview_marginalia_payload(
        self,
        *,
        file_hash: str | None = None,
        title: str = "Visible Match",
        authors: list[str] | None = None,
        session_status: str = "completed",
    ) -> dict[str, Any]:
        checksum = file_hash or self.visible.file.checksum
        authors = ["Author One"] if authors is None else authors
        return {
            "type": "SecondPassMarginaliaExport",
            "schema_version": "0.1.0",
            "profile": "https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0",
            "generated_at": "2026-06-07T12:00:00+00:00",
            "generator": "Second Pass Library",
            "scope": {"type": "book", "book": f"book:sha256:{checksum}"},
            "books": [
                {
                    "title": title,
                    "subtitle": "",
                    "authors": authors,
                    "series": "",
                    "series_index": None,
                    "language": "",
                    "isbn": "",
                    "epub_unique_identifier": "",
                    "source": f"book:sha256:{checksum}",
                    "file_hash": f"sha256:{checksum}",
                    "sessions": [
                        {
                            "export_session_id": "session-1",
                            "name": "Imported session",
                            "status": session_status,
                            "started_at": "2026-06-01T12:00:00+00:00",
                            "completed_at": "2026-06-02T12:00:00+00:00",
                            "created_at": "2026-06-01T12:00:00+00:00",
                            "updated_at": "2026-06-02T12:00:00+00:00",
                            "notes": "",
                            "progress": None,
                            "annotations": [
                                self.bookmark_entry(),
                                self.preview_highlight_entry("plain highlight", False),
                                self.preview_highlight_entry("commented highlight", True),
                            ],
                        }
                    ],
                }
            ],
        }

    def marginalia_payload(
        self,
        *,
        checksum: str | None = None,
        title: str = "Visible Match",
        status_value: str = "completed",
    ) -> dict[str, Any]:
        checksum = checksum or self.visible.file.checksum
        return {
            "type": "SecondPassMarginaliaExport",
            "schema_version": "0.1.0",
            "profile": "https://secondpasslibrary.local/specs/reading-session-annotations/0.1.0",
            "generated_at": "2026-06-07T12:00:00+00:00",
            "generator": "Second Pass Library",
            "scope": {"type": "book", "book": f"book:sha256:{checksum}"},
            "books": [
                {
                    "title": title,
                    "subtitle": "",
                    "authors": ["Author One"],
                    "series": "",
                    "series_index": None,
                    "language": "",
                    "isbn": "",
                    "epub_unique_identifier": "",
                    "source": f"book:sha256:{checksum}",
                    "file_hash": f"sha256:{checksum}",
                    "sessions": [
                        {
                            "export_session_id": "session-1",
                            "name": "Imported session",
                            "status": status_value,
                            "started_at": "2026-06-01T12:00:00+00:00",
                            "completed_at": None if status_value == "active" else "2026-06-02T12:00:00+00:00",
                            "created_at": "2026-06-01T12:00:00+00:00",
                            "updated_at": "2026-06-03T12:00:00+00:00",
                            "notes": "session notes",
                            "progress": None,
                            "annotations": [
                                self.bookmark_entry(),
                                self.highlight_entry(),
                                self.commented_highlight_entry(),
                            ],
                        }
                    ],
                }
            ],
        }

    def bookmark_entry(self) -> dict[str, Any]:
        return {
            "motivation": ["bookmarking"],
            "target": {"selector": {"type": "FragmentSelector", "value": "epubcfi(/6/2)"}},
            "body": [],
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def preview_highlight_entry(self, text: str, commented: bool) -> dict[str, Any]:
        body = [
            {
                "type": "TextualBody",
                "purpose": "describing",
                "value": text,
                "color": "yellow",
            }
        ]
        motivations = ["highlighting"]
        if commented:
            motivations.append("commenting")
            body.append({"type": "TextualBody", "purpose": "commenting", "value": "note"})
        return {
            "motivation": motivations,
            "target": {"selector": {"type": "FragmentSelector", "value": "epubcfi(/6/4)"}},
            "body": body,
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def highlight_entry(self) -> dict[str, Any]:
        return {
            "motivation": ["highlighting"],
            "target": {
                "selector": [
                    {"type": "FragmentSelector", "value": "epubcfi(/6/4)"},
                    {
                        "type": "TextQuoteSelector",
                        "exact": "plain highlight",
                        "prefix": "before ",
                        "suffix": " after",
                    },
                ]
            },
            "body": [
                {
                    "type": "TextualBody",
                    "purpose": "describing",
                    "value": "plain highlight",
                    "color": "green",
                }
            ],
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }

    def commented_highlight_entry(self) -> dict[str, Any]:
        return {
            "motivation": ["highlighting", "commenting"],
            "target": {"selector": {"type": "FragmentSelector", "value": "epubcfi(/6/8)"}},
            "body": [
                {
                    "type": "TextualBody",
                    "purpose": "describing",
                    "value": "commented highlight",
                    "color": "yellow",
                },
                {"type": "TextualBody", "purpose": "commenting", "value": "note"},
            ],
            "is_deleted": False,
            "created_at": "2026-06-01T12:00:00+00:00",
            "updated_at": "2026-06-01T12:00:00+00:00",
        }
