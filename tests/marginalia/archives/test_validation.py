from __future__ import annotations

import copy
import json

from django.test import SimpleTestCase

from marginalia.archives import (
    ArchiveValidationError,
    MalformedArchiveError,
    UnsupportedArchiveProfileError,
    parse_archive,
)
from marginalia.profile import MARGINALIA_PROFILE_URI


class MarginaliaArchiveValidationTests(SimpleTestCase):
    def test_valid_archive_parses_to_immutable_bounded_values(self):
        payload = _valid_archive()
        payload["books"][0]["readingSessions"][0]["progress"]["cfi"] = (
            "  opaque::progress  "
        )
        payload["books"][0]["readingSessions"][0]["progress"][
            "locationLabel"
        ] = "  Chapter 08 · 42% · Decorative suffix  "

        parsed = parse_archive(json.dumps(payload).encode())

        progress = parsed.books[0].reading_sessions[0].progress
        self.assertEqual(progress.cfi, "  opaque::progress  ")
        self.assertEqual(
            progress.location_label,
            "  Chapter 08 · 42% · Decorative suffix  ",
        )
        self.assertEqual(parsed.books[0].reading_sessions[0].status, "closed")

    def test_active_and_closed_lifecycle_and_optional_labels_are_accepted(self):
        active = _valid_archive()
        _session(active)["status"] = "active"
        _session(active)["closedAt"] = None
        _session(active)["progress"].pop("locationLabel")
        closed = _valid_archive()

        active_value = parse_archive(json.dumps(active))
        closed_value = parse_archive(json.dumps(closed))

        self.assertEqual(active_value.books[0].reading_sessions[0].status, "active")
        self.assertIsNone(
            active_value.books[0].reading_sessions[0].progress.location_label
        )
        self.assertEqual(closed_value.books[0].reading_sessions[0].status, "closed")

    def test_retired_lifecycle_progress_and_selector_shapes_are_rejected(self):
        for label, mutate in (
            ("completed", lambda value: _session(value).__setitem__("status", "completed")),
            ("archived", lambda value: _session(value).__setitem__("status", "archived")),
            (
                "numeric progress",
                lambda value: _session(value).__setitem__("progress", {"progression": 0.5}),
            ),
            (
                "W3C selector",
                lambda value: _annotation(value).__setitem__(
                    "target", {"selector": {"type": "FragmentSelector", "value": "opaque"}}
                ),
            ),
        ):
            payload = _valid_archive()
            mutate(payload)
            with self.subTest(label=label), self.assertRaises(ArchiveValidationError):
                parse_archive(json.dumps(payload))

    def test_ambiguous_or_missing_identity_fields_are_rejected(self):
        mutations = (
            lambda value: value["books"][0].__setitem__("id", "ambiguous"),
            lambda value: _session(value).__setitem__("id", "ambiguous"),
            lambda value: _session(value).pop("sourceReadingSessionId"),
            lambda value: _annotation(value).__setitem__("id", "ambiguous"),
            lambda value: _annotation(value).pop("clientAnnotationId"),
            lambda value: value["books"][0].__setitem__("source", "not-portable"),
            lambda value: value["books"][0].pop("fileHash"),
        )
        for mutate in mutations:
            payload = _valid_archive()
            mutate(payload)
            with self.subTest(mutate=mutate), self.assertRaises(ArchiveValidationError):
                parse_archive(json.dumps(payload))

    def test_strict_annotation_shapes_are_enforced(self):
        bookmark_with_body = _valid_archive()
        bookmark_with_body["books"][0]["readingSessions"][0]["annotations"].append(
            {
                "clientAnnotationId": "bookmark-1",
                "kind": "bookmark",
                "location": {"cfi": "opaque::bookmark"},
                "body": {"text": "invalid", "color": "yellow"},
                "createdAt": "2026-07-29T11:00:00Z",
                "updatedAt": "2026-07-29T11:00:00Z",
            }
        )
        highlight_without_text = _valid_archive()
        _annotation(highlight_without_text)["body"].pop("text")
        unknown_field = _valid_archive()
        _annotation(unknown_field)["unexpected"] = True

        for payload in (bookmark_with_body, highlight_without_text, unknown_field):
            with self.subTest(payload=payload), self.assertRaises(ArchiveValidationError):
                parse_archive(json.dumps(payload))

    def test_duplicate_explicit_identities_follow_archive_identity_rules(self):
        duplicate_book = _valid_archive()
        duplicate_book["books"].append(copy.deepcopy(duplicate_book["books"][0]))

        duplicate_session = _valid_archive()
        duplicate_session["books"][0]["readingSessions"].append(
            copy.deepcopy(_session(duplicate_session))
        )

        duplicate_annotation = _valid_archive()
        duplicate_annotation["books"][0]["readingSessions"][0][
            "annotations"
        ].append(copy.deepcopy(_annotation(duplicate_annotation)))

        for payload in (duplicate_book, duplicate_session, duplicate_annotation):
            with self.subTest(payload=payload), self.assertRaises(ArchiveValidationError):
                parse_archive(json.dumps(payload))

        cross_session = _valid_archive()
        second = copy.deepcopy(_session(cross_session))
        second["sourceReadingSessionId"] = "source-session-2"
        cross_session["books"][0]["readingSessions"].append(second)
        parsed = parse_archive(json.dumps(cross_session))
        self.assertEqual(len(parsed.books[0].reading_sessions), 2)

    def test_profile_mismatch_and_malformed_json_use_focused_errors(self):
        payload = _valid_archive()
        payload["profile"] = "https://example.invalid/profile"
        with self.assertRaises(UnsupportedArchiveProfileError):
            parse_archive(json.dumps(payload))
        with self.assertRaises(MalformedArchiveError):
            parse_archive(b"{not-json")


def _valid_archive():
    return {
        "type": "SecondPassMarginaliaExport",
        "schemaVersion": "0.1.0",
        "profile": MARGINALIA_PROFILE_URI,
        "generatedAt": "2026-07-30T12:00:00Z",
        "generator": "Second Pass Library",
        "books": [
            {
                "fileHash": f"sha256:{'a' * 64}",
                "title": "Archive Book",
                "authors": ["Example Author"],
                "readingSessions": [
                    {
                        "sourceReadingSessionId": "source-session-1",
                        "name": "Second pass",
                        "notes": "Session notes",
                        "status": "closed",
                        "startedAt": "2026-07-01T12:00:00Z",
                        "closedAt": "2026-07-20T12:00:00Z",
                        "createdAt": "2026-07-01T12:00:00Z",
                        "updatedAt": "2026-07-20T12:00:00Z",
                        "progress": {
                            "cfi": "opaque::progress",
                            "locationLabel": "Chapter 08 · 42%",
                            "updatedAt": "2026-07-19T12:00:00Z",
                        },
                        "annotations": [
                            {
                                "clientAnnotationId": "highlight-1",
                                "kind": "highlight",
                                "location": {
                                    "cfi": "opaque::highlight",
                                    "locationLabel": "Chapter 08 · 42%",
                                },
                                "body": {
                                    "text": "Selected passage",
                                    "color": "yellow",
                                },
                                "createdAt": "2026-07-18T12:00:00Z",
                                "updatedAt": "2026-07-18T12:00:00Z",
                            }
                        ],
                    }
                ],
            }
        ],
    }


def _session(value):
    return value["books"][0]["readingSessions"][0]


def _annotation(value):
    return _session(value)["annotations"][0]
