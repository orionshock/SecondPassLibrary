from __future__ import annotations

from io import BytesIO
import hashlib
import json

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from library.imports.epub import import_epub_file
from library.imports.results import IMPORT_STATUS_IMPORTED
from marginalia.exports.services import export_all_marginalia
from marginalia.imports.services import preview_import
from marginalia.models import Annotation, ReadingSession
from tests.library.imports.helpers import epub_with_cover_bytes, image_bytes
from tests.testenv.filesystem import IsolatedUserdataMixin


User = get_user_model()


class MarginaliaChecksumRoundTripTests(IsolatedUserdataMixin, TestCase):
    def test_exact_epub_bytes_round_trip_from_library_import_to_marginalia_preview(
        self,
    ):
        epub_bytes = epub_with_cover_bytes(cover_bytes=image_bytes())
        filename = "synthetic-cover.epub"
        user = User.objects.create_superuser(
            username="owner",
            password="testpass",
            email="owner@example.com",
        )
        first_import = import_epub_file(
            BytesIO(epub_bytes),
            source_filename=filename,
            actor=user,
        )
        self.assertEqual(first_import.status, IMPORT_STATUS_IMPORTED)
        original_book = first_import.book
        session = ReadingSession.objects.create(user=user, book=original_book)
        Annotation.objects.create(
            session=session,
            client_id="round-trip-highlight",
            kind=Annotation.KIND_HIGHLIGHT,
            location="epubcfi(/6/2!/4/2)",
            highlight_text="Selected fixture text",
        )

        exported = export_all_marginalia(user=user)
        archive = json.loads(exported.content)
        expected_checksum = hashlib.sha256(epub_bytes).hexdigest()
        self.assertEqual(original_book.checksum, expected_checksum)
        self.assertEqual(archive["books"][0]["fileHash"], f"sha256:{expected_checksum}")

        session.delete()
        original_book.delete()
        second_import = import_epub_file(
            BytesIO(epub_bytes),
            source_filename=filename,
            actor=user,
        )
        self.assertEqual(second_import.status, IMPORT_STATUS_IMPORTED)
        self.assertEqual(second_import.book.checksum, expected_checksum)

        preview = preview_import(
            user=user,
            file=SimpleUploadedFile(
                "round-trip.json",
                exported.content,
                content_type="application/json",
            ),
        )

        self.assertEqual(preview["matched_book_count"], 1)
        match = preview["books"][0]["match"]
        self.assertEqual(match["status"], "matched")
        self.assertEqual(match["book_id"], str(second_import.book.pk))
        self.assertIn(
            second_import.book.cover_file.name.replace("\\", "/"),
            match["cover_url"],
        )
