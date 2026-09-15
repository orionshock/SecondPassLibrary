from __future__ import annotations

# Intentionally cohesive despite its size - however eval deep if any additions really belong here or in another file.
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from marginalia.archives import ArchiveBook, ArchiveReadingSession, MarginaliaArchive
from marginalia.imports._plan_schema import (
    BOOK_INACCESSIBLE,
    IMPORT_STATUS,
    MATCHED,
    UNMATCHED,
    UNMATCHED_REASONS,
    StagedImportPlanError,
)
from marginalia.imports._plan_schema import (
    decode_and_index as _decode_and_index,
)
from marginalia.imports._plan_schema import (
    text as _text,
)
from marginalia.imports._plan_schema import (
    validate_and_index as _validate_and_index,
)
from marginalia.imports._plan_schema import (
    validate_session as _validate_session,
)

UNTITLED_BOOK = "Untitled Book"


class StagedImportSelectionError(StagedImportPlanError):
    pass


@dataclass(frozen=True, slots=True)
class PlanSelection:
    candidate_id: str
    name: str
    notes: str


@dataclass(frozen=True, slots=True)
class ResolvedSelection:
    candidate_id: str
    book_candidate_id: str
    book_id: str
    staged_book_title: str
    source: ArchiveReadingSession
    name: str
    notes: str
    possible_duplicate: bool


class StagedImportPlan:
    """Own the staged plan's private JSON structure and its interpretation."""

    def __init__(self) -> None:
        self._books: list[dict] = []
        self._warnings: list[dict] = []
        self._books_by_candidate_id: dict[str, dict] = {}
        self._candidates_by_id: dict[str, tuple[dict, dict]] = {}
        self._candidate_ids_by_source_session_id: dict[str, str] = {}

    def add_book(
        self,
        *,
        file_hash: str,
        title: str,
        authors: Sequence[str],
        book_id: object | None = None,
        cover_url: str | None = None,
        unmatched_reason: str | None = None,
    ) -> str:
        _text(file_hash, allow_blank=True)
        _text(title, allow_blank=True)
        if isinstance(authors, str):
            raise StagedImportPlanError
        tuple(_text(author) for author in authors)
        if cover_url is not None and not isinstance(cover_url, str):
            raise StagedImportPlanError
        matched = book_id is not None
        if matched == (unmatched_reason is not None):
            raise StagedImportPlanError
        if unmatched_reason is not None and unmatched_reason not in UNMATCHED_REASONS:
            raise StagedImportPlanError
        if matched:
            _text(str(book_id))
        elif cover_url is not None:
            raise StagedImportPlanError
        candidate_id = f"book-{len(self._books) + 1:06d}"
        if candidate_id in self._books_by_candidate_id:
            raise StagedImportPlanError
        match = (
            {"status": MATCHED, "book_id": str(book_id), "cover_url": cover_url}
            if matched
            else {"status": UNMATCHED, "reason": unmatched_reason}
        )
        book = {
            "candidate_id": candidate_id,
            "file_hash": file_hash,
            "title": title,
            "authors": list(authors),
            "match": match,
            "reading_sessions": [],
        }
        self._books.append(book)
        self._books_by_candidate_id[candidate_id] = book
        return candidate_id

    def add_session(
        self,
        *,
        book_candidate_id: str,
        source_reading_session_id: str,
        name: str,
        notes: str,
        source_status: str,
        started_at: str,
        closed_at: str | None,
        annotation_count: int,
        possible_duplicate: bool,
    ) -> str:
        book = self._books_by_candidate_id.get(book_candidate_id)
        if book is None:
            raise StagedImportPlanError
        if source_reading_session_id in self._candidate_ids_by_source_session_id:
            raise StagedImportPlanError
        candidate_id = f"reading-session-{len(self._candidates_by_id) + 1:06d}"
        if candidate_id in self._candidates_by_id:
            raise StagedImportPlanError
        row = {
            "candidate_id": candidate_id,
            "source_reading_session_id": source_reading_session_id,
            "name": name,
            "notes": notes,
            "source_status": source_status,
            "will_import_as_status": IMPORT_STATUS,
            "started_at": started_at,
            "closed_at": closed_at,
            "annotation_count": annotation_count,
            "will_import": book["match"]["status"] == MATCHED,
            "possible_duplicate": possible_duplicate,
        }
        _text(source_reading_session_id)
        _validate_session(row, matched=book["match"]["status"] == MATCHED)
        book["reading_sessions"].append(row)
        self._candidates_by_id[candidate_id] = (book, row)
        self._candidate_ids_by_source_session_id[source_reading_session_id] = (
            candidate_id
        )
        return candidate_id

    def add_warning(self, *, code: str, message: str, candidate_id: str) -> None:
        _text(code)
        _text(message)
        if candidate_id not in self._candidates_by_id:
            raise StagedImportPlanError
        self._warnings.append(
            {"code": code, "message": message, "candidate_id": candidate_id}
        )

    @property
    def unmatched_session_count(self) -> int:
        return sum(
            not row["will_import"] for _book, row in self._candidates_by_id.values()
        )

    def encode(self) -> dict:
        _book_index, candidates, _source_index = _validate_and_index(
            self._books,
            self._warnings,
        )
        return self._encoded(candidates)

    def _encoded(self, candidates: Mapping[str, tuple[dict, dict]]) -> dict:
        unmatched_count = self.unmatched_session_count
        return {
            "can_apply": any(row["will_import"] for _book, row in candidates.values()),
            "summary": {
                "book_count": len(self._books),
                "reading_session_count": len(candidates),
                "annotation_count": sum(
                    row["annotation_count"] for _book, row in candidates.values()
                ),
            },
            "matched_book_count": sum(
                book["match"]["status"] == MATCHED for book in self._books
            ),
            "unmatched_book_count": sum(
                book["match"]["status"] == UNMATCHED
                or any(row.get("unmatched_reason") for row in book["reading_sessions"])
                for book in self._books
            ),
            "unmatched_reading_session_count": unmatched_count,
            "unmatched_downloadable_reading_session_count": unmatched_count,
            "warnings": deepcopy(self._warnings),
            "books": deepcopy(self._books),
        }

    @classmethod
    def decode(cls, persisted: object) -> StagedImportPlan:
        try:
            (
                value,
                books,
                warnings,
                book_index,
                candidate_index,
                source_index,
            ) = _decode_and_index(persisted)
            plan = cls()
            plan._books = books
            plan._warnings = warnings
            plan._books_by_candidate_id = book_index
            plan._candidates_by_id = candidate_index
            plan._candidate_ids_by_source_session_id = source_index
            encoded = plan._encoded(candidate_index)
            derived_keys = (
                "can_apply",
                "summary",
                "matched_book_count",
                "unmatched_book_count",
                "unmatched_reading_session_count",
                "unmatched_downloadable_reading_session_count",
            )
            if any(value.get(key) != encoded[key] for key in derived_keys):
                raise StagedImportPlanError
            return plan
        except StagedImportPlanError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise StagedImportPlanError from exc

    def normalize_selections(
        self,
        requested: Sequence[Mapping[str, Any]],
        *,
        allow_applied_inaccessible: bool,
    ) -> tuple[PlanSelection, ...]:
        normalized = []
        seen = set()
        try:
            for raw in requested:
                candidate_id = _text(raw["candidate_id"])
                context = self._candidates_by_id.get(candidate_id)
                if candidate_id in seen or context is None:
                    raise StagedImportSelectionError
                seen.add(candidate_id)
                book, candidate = context
                eligible = book["match"]["status"] == MATCHED and (
                    candidate["will_import"]
                    or (
                        allow_applied_inaccessible
                        and candidate.get("unmatched_reason") == BOOK_INACCESSIBLE
                    )
                )
                if not eligible:
                    raise StagedImportSelectionError
                normalized.append(
                    PlanSelection(
                        candidate_id=candidate_id,
                        name=_text(
                            raw.get("name", candidate["name"]), allow_blank=True
                        ),
                        notes=_text(
                            raw.get("notes", candidate["notes"]), allow_blank=True
                        ),
                    )
                )
        except StagedImportSelectionError:
            raise
        except (KeyError, TypeError, ValueError) as exc:
            raise StagedImportSelectionError from exc
        return tuple(sorted(normalized, key=lambda item: item.candidate_id))

    def resolve_selections(
        self,
        *,
        archive: MarginaliaArchive,
        selections: tuple[PlanSelection, ...],
        include_empty_sessions: bool,
    ) -> tuple[ResolvedSelection, ...]:
        aligned = self._aligned_books(
            archive=archive,
            include_empty_sessions=include_empty_sessions,
        )
        sources = {
            row["candidate_id"]: source_sessions[row["source_reading_session_id"]]
            for book, _source_book, source_sessions in aligned
            for row in book["reading_sessions"]
        }
        resolved = []
        for selection in selections:
            book, row = self._candidates_by_id[selection.candidate_id]
            book_id = book["match"].get("book_id")
            if not book_id:
                raise StagedImportPlanError
            resolved.append(
                ResolvedSelection(
                    candidate_id=selection.candidate_id,
                    book_candidate_id=book["candidate_id"],
                    book_id=book_id,
                    staged_book_title=book["title"],
                    source=sources[selection.candidate_id],
                    name=selection.name,
                    notes=selection.notes,
                    possible_duplicate=row["possible_duplicate"],
                )
            )
        return tuple(resolved)

    def with_access_lost(self, candidate_ids: set[str]) -> StagedImportPlan:
        updated = StagedImportPlan.decode(self.encode())
        if not candidate_ids.issubset(updated._candidates_by_id):
            raise StagedImportPlanError
        for candidate_id in candidate_ids:
            _book, candidate = updated._candidates_by_id[candidate_id]
            candidate["will_import"] = False
            candidate["unmatched_reason"] = BOOK_INACCESSIBLE
        return updated

    def unmatched_summaries(self) -> list[dict]:
        rows = []
        for book in self._books:
            reason = book["match"].get("reason")
            if reason is None and any(
                row.get("unmatched_reason") == BOOK_INACCESSIBLE
                for row in book["reading_sessions"]
            ):
                reason = BOOK_INACCESSIBLE
            if reason is not None:
                rows.append(
                    {
                        "candidate_id": book["candidate_id"],
                        "title": " ".join(book["title"].split()) or UNTITLED_BOOK,
                        "reason": reason,
                    }
                )
        return rows

    def unmatched_archive_books(
        self,
        *,
        archive: MarginaliaArchive,
        include_empty_sessions: bool,
    ) -> tuple[tuple[ArchiveBook, tuple[ArchiveReadingSession, ...]], ...]:
        results = []
        for book, source_book, sources in self._aligned_books(
            archive=archive,
            include_empty_sessions=include_empty_sessions,
        ):
            sessions = tuple(
                sources[row["source_reading_session_id"]]
                for row in book["reading_sessions"]
                if not row["will_import"]
            )
            if sessions:
                results.append((source_book, sessions))
        if (
            sum(len(sessions) for _book, sessions in results)
            != self.unmatched_session_count
        ):
            raise StagedImportPlanError
        return tuple(results)

    def _aligned_books(self, *, archive, include_empty_sessions: bool) -> tuple:
        archive_books = tuple(
            book
            for book in archive.books
            if any(
                include_empty_sessions or row.annotations
                for row in book.reading_sessions
            )
        )
        if len(archive_books) != len(self._books):
            raise StagedImportPlanError
        aligned = []
        for book, source_book in zip(self._books, archive_books, strict=True):
            sources = {
                row.source_reading_session_id: row
                for row in source_book.reading_sessions
            }
            expected_ids = tuple(
                row.source_reading_session_id
                for row in source_book.reading_sessions
                if include_empty_sessions or row.annotations
            )
            rows = book["reading_sessions"]
            if (
                source_book.file_hash != book["file_hash"]
                or tuple(row["source_reading_session_id"] for row in rows)
                != expected_ids
            ):
                raise StagedImportPlanError
            if any(
                row["source_status"] != sources[row["source_reading_session_id"]].status
                or row["annotation_count"]
                != len(sources[row["source_reading_session_id"]].annotations)
                for row in rows
            ):
                raise StagedImportPlanError
            aligned.append((book, source_book, sources))
        return tuple(aligned)
