from unittest.mock import patch

from django.test import SimpleTestCase

from marginalia.archives import (
    ArchiveBook,
    ArchiveBookmark,
    ArchiveReadingSession,
    MarginaliaArchive,
)
from marginalia.imports import plan as plan_module
from marginalia.imports.plan import (
    BOOK_INACCESSIBLE,
    StagedImportPlan,
    StagedImportPlanError,
)


def _plan() -> tuple[StagedImportPlan, str, str]:
    plan = StagedImportPlan()
    matched_book = plan.add_book(
        file_hash=f"sha256:{'a' * 64}",
        title="Matched",
        authors=("First Author",),
        book_id="book-id",
    )
    first = plan.add_session(
        book_candidate_id=matched_book,
        source_reading_session_id="source-1",
        name="Session 1",
        notes="Notes",
        source_status="active",
        started_at="2026-07-19T12:00:00Z",
        closed_at=None,
        annotation_count=1,
        possible_duplicate=True,
    )
    plan.add_warning(
        code="POSSIBLE_DUPLICATE_SESSION",
        message="A similar Reading Session already exists.",
        candidate_id=first,
    )
    unmatched_book = plan.add_book(
        file_hash=f"sha256:{'b' * 64}",
        title="Missing",
        authors=("Second Author",),
        unmatched_reason="not_found",
    )
    second = plan.add_session(
        book_candidate_id=unmatched_book,
        source_reading_session_id="source-2",
        name="Session 2",
        notes="Notes",
        source_status="active",
        started_at="2026-07-19T12:00:00Z",
        closed_at=None,
        annotation_count=2,
        possible_duplicate=False,
    )
    return plan, first, second


def _add_sessions(
    plan: StagedImportPlan, book_candidate_id: str, count: int
) -> list[str]:
    return [
        plan.add_session(
            book_candidate_id=book_candidate_id,
            source_reading_session_id=f"source-{number}",
            name=f"Session {number}",
            notes="",
            source_status="active",
            started_at="2026-07-19T12:00:00Z",
            closed_at=None,
            annotation_count=0,
            possible_duplicate=False,
        )
        for number in range(1, count + 1)
    ]


def _archive_session(source_id: str, annotation_count: int) -> ArchiveReadingSession:
    return ArchiveReadingSession(
        source_reading_session_id=source_id,
        name=source_id,
        notes="",
        status="active",
        started_at="2026-07-19T12:00:00Z",
        closed_at=None,
        created_at="2026-07-19T12:00:00Z",
        updated_at="2026-07-19T12:00:00Z",
        progress=None,
        annotations=tuple(
            ArchiveBookmark(
                client_annotation_id=f"{source_id}-{number}",
                location_cfi="cfi",
                location_label=None,
                created_at="2026-07-19T12:00:00Z",
                updated_at="2026-07-19T12:00:00Z",
            )
            for number in range(annotation_count)
        ),
    )


def _archive() -> MarginaliaArchive:
    return MarginaliaArchive(
        type="SecondPassMarginaliaExport",
        schema_version="0.1.0",
        profile="profile",
        generated_at="2026-07-19T12:00:00Z",
        generator="test",
        books=(
            ArchiveBook(
                file_hash=f"sha256:{'a' * 64}",
                title="Matched",
                authors=("First Author",),
                reading_sessions=(_archive_session("source-1", 1),),
            ),
            ArchiveBook(
                file_hash=f"sha256:{'b' * 64}",
                title="Missing",
                authors=("Second Author",),
                reading_sessions=(_archive_session("source-2", 2),),
            ),
        ),
    )


class StagedImportPlanTests(SimpleTestCase):
    def test_durable_representation_round_trip_preserves_identity_order_and_counts(
        self,
    ):
        plan, first, second = _plan()

        encoded = plan.encode()
        decoded = StagedImportPlan.decode(encoded)

        self.assertEqual(decoded.encode(), encoded)
        self.assertEqual(
            [
                session["candidate_id"]
                for book in decoded.encode()["books"]
                for session in book["reading_sessions"]
            ],
            [first, second],
        )
        self.assertEqual(encoded["summary"]["annotation_count"], 3)
        self.assertEqual(encoded["matched_book_count"], 1)
        self.assertEqual(encoded["unmatched_book_count"], 1)
        self.assertEqual(encoded["unmatched_reading_session_count"], 1)

    def test_access_loss_is_an_owned_immutable_transition(self):
        plan, candidate_id, _second = _plan()

        updated = plan.with_access_lost({candidate_id})

        original = plan.encode()["books"][0]["reading_sessions"][0]
        candidate = updated.encode()["books"][0]["reading_sessions"][0]
        self.assertTrue(original["will_import"])
        self.assertFalse(candidate["will_import"])
        self.assertEqual(candidate["unmatched_reason"], BOOK_INACCESSIBLE)
        self.assertEqual(updated.unmatched_session_count, 2)

    def test_controlled_construction_rejects_an_impossible_match(self):
        plan = StagedImportPlan()

        with self.assertRaises(StagedImportPlanError):
            plan.add_book(
                file_hash=f"sha256:{'a' * 64}",
                title="Invalid",
                authors=(),
                book_id="book-id",
                unmatched_reason="not_found",
            )

    def test_decode_rejects_inconsistent_derived_projection(self):
        plan, _first, _second = _plan()
        encoded = plan.encode()
        encoded["summary"]["reading_session_count"] = 99

        with self.assertRaises(StagedImportPlanError):
            StagedImportPlan.decode(encoded)

    def test_large_construction_preserves_candidate_identity_order_and_encoding(self):
        plan = StagedImportPlan()
        book = plan.add_book(
            file_hash=f"sha256:{'a' * 64}",
            title="Large plan",
            authors=("Author",),
            book_id="book-id",
        )

        candidate_ids = _add_sessions(plan, book, 1000)
        encoded = plan.encode()

        self.assertEqual(candidate_ids[0], "reading-session-000001")
        self.assertEqual(candidate_ids[-1], "reading-session-001000")
        self.assertEqual(
            [row["candidate_id"] for row in encoded["books"][0]["reading_sessions"]],
            candidate_ids,
        )
        self.assertEqual(StagedImportPlan.decode(encoded).encode(), encoded)

    def test_incremental_source_index_still_rejects_duplicate_identity(self):
        plan, _first, _second = _plan()

        with self.assertRaises(StagedImportPlanError):
            plan.add_session(
                book_candidate_id="book-000002",
                source_reading_session_id="source-1",
                name="Duplicate",
                notes="",
                source_status="active",
                started_at="2026-07-19T12:00:00Z",
                closed_at=None,
                annotation_count=0,
                possible_duplicate=False,
            )

    def test_decoded_indexes_support_selection_access_loss_and_unmatched_projection(
        self,
    ):
        plan, first, _second = _plan()
        decoded = StagedImportPlan.decode(plan.encode())
        archive = _archive()

        selections = decoded.normalize_selections(
            [{"candidate_id": first}],
            allow_applied_inaccessible=False,
        )
        resolved = decoded.resolve_selections(
            archive=archive,
            selections=selections,
            include_empty_sessions=True,
        )
        updated = decoded.with_access_lost({first})
        unmatched = updated.unmatched_archive_books(
            archive=archive,
            include_empty_sessions=True,
        )

        self.assertEqual(resolved[0].source.source_reading_session_id, "source-1")
        self.assertEqual(
            [
                session.source_reading_session_id
                for _book, sessions in unmatched
                for session in sessions
            ],
            ["source-1", "source-2"],
        )

    def test_construction_does_not_rebuild_candidate_indexes_as_sessions_grow(self):
        with patch.object(
            plan_module,
            "_validate_and_index",
            wraps=plan_module._validate_and_index,
        ) as rebuild:
            validation_traversals = []
            for session_count in (10, 100, 1000):
                plan = StagedImportPlan()
                book = plan.add_book(
                    file_hash="hash",
                    title="Book",
                    authors=(),
                    book_id="book-id",
                )
                _add_sessions(plan, book, session_count)
                prior_traversals = rebuild.call_count
                plan.encode()
                validation_traversals.append(rebuild.call_count - prior_traversals)

            self.assertEqual(validation_traversals, [1, 1, 1])
