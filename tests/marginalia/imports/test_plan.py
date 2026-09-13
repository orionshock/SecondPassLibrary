from django.test import SimpleTestCase

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


class StagedImportPlanTests(SimpleTestCase):
    def test_durable_representation_round_trip_preserves_identity_order_and_counts(self):
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
