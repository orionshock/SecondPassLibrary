from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.client_api import hash_client_secret
from accounts.models import UserClientSession
from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import (
    Author,
    Book,
    BookFile,
    BookGroupAssignment,
    LibraryGroup,
    Series,
)

from tests.library.utils import IsolatedMediaRootMixin, paginated_results


class ClientBearerLibraryReadOnlyAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.user)

        self.token = "spl_testtoken_library"
        UserClientSession.objects.create(
            user=self.user,
            name="Reader",
            client_type="reader",
            token_hash=hash_client_secret(self.token),
            last_seen_at=None,
            expires_at=None,
            revoked_at=None,
        )

        self.author = Author.objects.create(name="A Author")
        self.series = Series.objects.create(name="S Series")

        self.public_book = Book.objects.create(
            title="Public Book",
            language="en",
            series=self.series,
            series_index=1,
        )
        self.public_book.authors.add(self.author)
        ensure_book_public_assignment(book=self.public_book, added_by=None)
        uploaded = SimpleUploadedFile(
            "ignored.epub",
            b"epub-bytes",
            content_type="application/epub+zip",
        )
        self.public_file = BookFile.objects.create(
            book=self.public_book,
            file=uploaded,
            checksum="a" * 64,
            file_size=9,
            source_filename="SOURCE.epub",
        )

        self.hidden_group = LibraryGroup.objects.create(name="Hidden")
        self.hidden_book = Book.objects.create(title="Hidden Book")
        self.hidden_book.authors.add(self.author)
        BookGroupAssignment.objects.create(book=self.hidden_book, group=self.hidden_group)
        uploaded2 = SimpleUploadedFile(
            "ignored2.epub",
            b"epub-bytes-2",
            content_type="application/epub+zip",
        )
        self.hidden_file = BookFile.objects.create(
            book=self.hidden_book,
            file=uploaded2,
            checksum="b" * 64,
            file_size=11,
            source_filename="HIDDEN.epub",
        )

    @property
    def _auth_header(self) -> str:
        return f"Bearer {self.token}"

    def test_bearer_can_list_books(self):
        r = cast(
            Response,
            self.client.get(
                "/api/v1/library/books/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        titles = sorted([b["title"] for b in paginated_results(r)])
        self.assertEqual(titles, ["Public Book"])

    def test_bearer_can_retrieve_accessible_book_and_404_inaccessible(self):
        ok = cast(
            Response,
            self.client.get(
                f"/api/v1/library/books/{self.public_book.id}/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], ok.data)
        self.assertEqual(payload["id"], str(self.public_book.id))

        hidden = self.client.get(
            f"/api/v1/library/books/{self.hidden_book.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_bearer_can_download_accessible_file_and_404_inaccessible(self):
        ok = self.client.get(
            f"/api/v1/library/book-files/{self.public_file.id}/download/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(ok.status_code, status.HTTP_200_OK)
        self.assertEqual(ok.get("Content-Type"), "application/epub+zip")

        hidden = self.client.get(
            f"/api/v1/library/book-files/{self.hidden_file.id}/download/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(hidden.status_code, status.HTTP_404_NOT_FOUND)

    def test_bearer_can_use_common_book_filters(self):
        r1 = cast(
            Response,
            self.client.get(
                "/api/v1/library/books/?q=Public",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual([b["title"] for b in paginated_results(r1)], ["Public Book"])

        r2 = cast(
            Response,
            self.client.get(
                "/api/v1/library/books/?has_files=true",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual([b["title"] for b in paginated_results(r2)], ["Public Book"])

        r3 = cast(
            Response,
            self.client.get(
                "/api/v1/library/books/?ordering=-updated_at",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)

    def test_bearer_can_read_authors_series_groups(self):
        authors = cast(
            Response,
            self.client.get(
                "/api/v1/library/authors/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(authors.status_code, status.HTTP_200_OK)
        names = [a["name"] for a in paginated_results(authors)]
        self.assertIn("A Author", names)

        author_detail = self.client.get(
            f"/api/v1/library/authors/{self.author.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(author_detail.status_code, status.HTTP_200_OK)

        series = cast(
            Response,
            self.client.get(
                "/api/v1/library/series/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(series.status_code, status.HTTP_200_OK)

        series_detail = self.client.get(
            f"/api/v1/library/series/{self.series.id}/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(series_detail.status_code, status.HTTP_200_OK)

        groups = cast(
            Response,
            self.client.get(
                "/api/v1/library/groups/",
                HTTP_AUTHORIZATION=self._auth_header,
            ),
        )
        self.assertEqual(groups.status_code, status.HTTP_200_OK)
        # Only Public should be visible to this user.
        group_names = [g["name"] for g in paginated_results(groups)]
        self.assertIn("Public", group_names)
        self.assertNotIn("Hidden", group_names)

    def test_bearer_mutations_are_rejected(self):
        patch = self.client.patch(
            f"/api/v1/library/books/{self.public_book.id}/",
            data={"title": "X"},
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(patch.status_code, status.HTTP_403_FORBIDDEN)

        imports = self.client.post(
            "/api/v1/library/imports/",
            data={"file": SimpleUploadedFile("x.epub", b"x", content_type="application/epub+zip")},
            format="multipart",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(imports.status_code, status.HTTP_403_FORBIDDEN)

        group_books_add = self.client.post(
            f"/api/v1/library/groups/{self.hidden_group.id}/books/",
            data={"book": str(self.public_book.id)},
            format="json",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertEqual(group_books_add.status_code, status.HTTP_403_FORBIDDEN)

    def test_revoked_or_inactive_token_is_rejected_for_library_reads(self):
        UserClientSession.objects.filter(user=self.user).update(revoked_at=timezone.now())
        r = self.client.get(
            "/api/v1/library/books/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertIn(r.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        UserClientSession.objects.filter(user=self.user).update(revoked_at=None)
        r2 = self.client.get(
            "/api/v1/library/books/",
            HTTP_AUTHORIZATION=self._auth_header,
        )
        self.assertIn(r2.status_code, (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
