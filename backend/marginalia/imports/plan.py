from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from marginalia.archives import ArchiveBook, ArchiveReadingSession, MarginaliaArchive


MATCHED = "matched"
UNMATCHED = "unmatched"
BOOK_INACCESSIBLE = "book_inaccessible"
UNMATCHED_REASONS = frozenset({"not_found", "ambiguous_match", BOOK_INACCESSIBLE})
IMPORT_STATUS = "closed"
UNTITLED_BOOK = "Untitled Book"


class StagedImportPlanError(ValueError):
    pass


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
        match = (
            {"status": MATCHED, "book_id": str(book_id), "cover_url": cover_url}
            if matched
            else {"status": UNMATCHED, "reason": unmatched_reason}
        )
        self._books.append(
            {
                "candidate_id": candidate_id,
                "file_hash": file_hash,
                "title": title,
                "authors": list(authors),
                "match": match,
                "reading_sessions": [],
            }
        )
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
        book = self._book(book_candidate_id)
        if source_reading_session_id in {
            row["source_reading_session_id"]
            for row in self._candidate_rows().values()
        }:
            raise StagedImportPlanError
        candidate_id = f"reading-session-{len(self._candidate_rows()) + 1:06d}"
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
        return candidate_id

    def add_warning(self, *, code: str, message: str, candidate_id: str) -> None:
        _text(code)
        _text(message)
        if candidate_id not in self._candidate_rows():
            raise StagedImportPlanError
        self._warnings.append(
            {"code": code, "message": message, "candidate_id": candidate_id}
        )

    @property
    def can_apply(self) -> bool:
        return any(row["will_import"] for row in self._candidate_rows().values())

    @property
    def unmatched_session_count(self) -> int:
        return sum(not row["will_import"] for row in self._candidate_rows().values())

    def encode(self) -> dict:
        candidate_ids = _validate_books(self._books)
        _validate_warnings(self._warnings, candidate_ids=candidate_ids)
        sessions = self._candidate_rows()
        unmatched_count = self.unmatched_session_count
        return {
            "can_apply": self.can_apply,
            "summary": {
                "book_count": len(self._books),
                "reading_session_count": len(sessions),
                "annotation_count": sum(row["annotation_count"] for row in sessions.values()),
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
            value = _mapping(persisted)
            books = _list(value["books"])
            warnings = _list(value["warnings"])
            candidate_ids = _validate_books(books)
            _validate_warnings(warnings, candidate_ids=candidate_ids)
            plan = cls()
            plan._books = deepcopy(books)
            plan._warnings = deepcopy(warnings)
            encoded = plan.encode()
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
        candidates = self._candidate_rows()
        normalized = []
        seen = set()
        try:
            for raw in requested:
                candidate_id = _text(raw["candidate_id"])
                candidate = candidates.get(candidate_id)
                if candidate_id in seen or candidate is None:
                    raise StagedImportSelectionError
                seen.add(candidate_id)
                book = self._book_for_candidate(candidate_id)
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
                        name=_text(raw.get("name", candidate["name"]), allow_blank=True),
                        notes=_text(raw.get("notes", candidate["notes"]), allow_blank=True),
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
        candidates = self._candidate_rows()
        resolved = []
        for selection in selections:
            row = candidates[selection.candidate_id]
            book = self._book_for_candidate(selection.candidate_id)
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
        candidates = updated._candidate_rows()
        if not candidate_ids.issubset(candidates):
            raise StagedImportPlanError
        for candidate_id in candidate_ids:
            candidates[candidate_id]["will_import"] = False
            candidates[candidate_id]["unmatched_reason"] = BOOK_INACCESSIBLE
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
        if sum(len(sessions) for _book, sessions in results) != self.unmatched_session_count:
            raise StagedImportPlanError
        return tuple(results)

    def _aligned_books(self, *, archive, include_empty_sessions: bool) -> tuple:
        archive_books = tuple(
            book
            for book in archive.books
            if any(include_empty_sessions or row.annotations for row in book.reading_sessions)
        )
        if len(archive_books) != len(self._books):
            raise StagedImportPlanError
        aligned = []
        for book, source_book in zip(self._books, archive_books, strict=True):
            sources = {
                row.source_reading_session_id: row for row in source_book.reading_sessions
            }
            expected_ids = tuple(
                row.source_reading_session_id
                for row in source_book.reading_sessions
                if include_empty_sessions or row.annotations
            )
            rows = book["reading_sessions"]
            if source_book.file_hash != book["file_hash"] or tuple(
                row["source_reading_session_id"] for row in rows
            ) != expected_ids:
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

    def _candidate_rows(self) -> dict[str, dict]:
        return {
            row["candidate_id"]: row
            for book in self._books
            for row in book["reading_sessions"]
        }

    def _book(self, candidate_id: str) -> dict:
        for book in self._books:
            if book["candidate_id"] == candidate_id:
                return book
        raise StagedImportPlanError

    def _book_for_candidate(self, candidate_id: str) -> dict:
        for book in self._books:
            if any(row["candidate_id"] == candidate_id for row in book["reading_sessions"]):
                return book
        raise StagedImportPlanError


def _validate_books(books: list) -> set[str]:
    if not books:
        raise StagedImportPlanError
    book_ids = set()
    candidate_ids = set()
    source_ids = set()
    for raw_book in books:
        book = _mapping(raw_book)
        book_id = _text(book["candidate_id"])
        if book_id in book_ids:
            raise StagedImportPlanError
        book_ids.add(book_id)
        _text(book["file_hash"], allow_blank=True)
        _text(book["title"], allow_blank=True)
        tuple(_text(author) for author in _list(book["authors"]))
        match = _mapping(book["match"])
        status = _text(match["status"])
        if status == MATCHED:
            _text(match["book_id"])
            if match.get("reason") is not None:
                raise StagedImportPlanError
            if match.get("cover_url") is not None and not isinstance(match["cover_url"], str):
                raise StagedImportPlanError
        elif (
            status != UNMATCHED
            or _text(match["reason"]) not in UNMATCHED_REASONS
            or match.get("book_id") is not None
            or match.get("cover_url") is not None
        ):
            raise StagedImportPlanError
        sessions = _list(book["reading_sessions"])
        if not sessions:
            raise StagedImportPlanError
        for raw_session in sessions:
            row = _mapping(raw_session)
            candidate_id = _text(row["candidate_id"])
            source_id = _text(row["source_reading_session_id"])
            if candidate_id in candidate_ids or source_id in source_ids:
                raise StagedImportPlanError
            candidate_ids.add(candidate_id)
            source_ids.add(source_id)
            _validate_session(row, matched=status == MATCHED)
    return candidate_ids


def _validate_session(row: Mapping, *, matched: bool) -> None:
    _text(row["name"], allow_blank=True)
    _text(row["notes"], allow_blank=True)
    _text(row["source_status"])
    _text(row["started_at"])
    if row["closed_at"] is not None and not isinstance(row["closed_at"], str):
        raise StagedImportPlanError
    if row["will_import_as_status"] != IMPORT_STATUS:
        raise StagedImportPlanError
    count = row["annotation_count"]
    if not isinstance(count, int) or isinstance(count, bool) or count < 0:
        raise StagedImportPlanError
    if not isinstance(row["will_import"], bool) or not isinstance(row["possible_duplicate"], bool):
        raise StagedImportPlanError
    reason = row.get("unmatched_reason")
    if reason is not None and reason not in UNMATCHED_REASONS:
        raise StagedImportPlanError
    if matched and row["will_import"] == (reason is not None):
        raise StagedImportPlanError
    if not matched and (row["will_import"] or reason is not None):
        raise StagedImportPlanError


def _validate_warnings(warnings: list, *, candidate_ids: set[str]) -> None:
    for raw in warnings:
        warning = _mapping(raw)
        _text(warning["code"])
        _text(warning["message"])
        if _text(warning["candidate_id"]) not in candidate_ids:
            raise StagedImportPlanError


def _mapping(value: object) -> Mapping:
    if not isinstance(value, Mapping):
        raise StagedImportPlanError
    return value


def _list(value: object) -> list:
    if not isinstance(value, list):
        raise StagedImportPlanError
    return value


def _text(value: object, *, allow_blank: bool = False) -> str:
    if not isinstance(value, str) or (not allow_blank and not value):
        raise StagedImportPlanError
    return value
