from __future__ import annotations

from collections.abc import Mapping
from typing import Any, cast

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework import status
from rest_framework.response import Response
from rest_framework.test import APITestCase

from accounts.models import UserProfile
from library.group_services import ensure_book_public_assignment, ensure_user_public_membership
from library.models import Author, Book, BookFile, Series
from library.models import BookGroupAssignment
from library.models import BookIdentifier

from tests.library.utils import IsolatedMediaRootMixin, paginated_results


class LibraryAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="testuser", password="testpass")

    def test_authenticated_access_books(self):
        response = self.client.get("/api/v1/library/books/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_authenticated_access_authors(self):
        response = self.client.get("/api/v1/library/authors/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class BookListErgonomicsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="testuser", password="testpass")

        self.author = Author.objects.create(name="A Author")
        self.series = Series.objects.create(name="S Series")
        self.book = Book.objects.create(title="T", series=self.series, series_index=1)
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)
        BookIdentifier.objects.create(
            book=self.book,
            scheme=BookIdentifier.SCHEME_ISBN_13,
            value="9780123456472",
            source="epub",
            is_primary=True,
        )
        uploaded = SimpleUploadedFile(
            "ignored.epub",
            b"epub-bytes",
            content_type="application/epub+zip",
        )
        BookFile.objects.create(
            book=self.book,
            file=uploaded,
            checksum="a" * 64,
            file_size=9,
            source_filename="SOURCE_NAME.epub",
        )

    def test_book_list_includes_nested_summaries_and_no_raw_file_paths(self):
        response = cast(Response, self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = paginated_results(response)
        self.assertEqual(len(data), 1)
        book = data[0]

        self.assertIsInstance(book["authors"], list)
        self.assertEqual(book["authors"][0]["id"], str(self.author.id))
        self.assertEqual(book["authors"][0]["name"], "A Author")

        self.assertIsInstance(book["series"], dict)
        self.assertEqual(book["series"]["id"], str(self.series.id))
        self.assertEqual(book["series"]["name"], "S Series")

        self.assertIsInstance(book["identifiers"], list)
        self.assertEqual(book["identifiers"][0]["scheme"], "isbn_13")
        self.assertEqual(book["identifiers"][0]["source"], "epub")

        self.assertIsInstance(book["files"], list)
        file0 = book["files"][0]
        self.assertIn("download_url", file0)
        self.assertNotIn("file", file0)
        self.assertNotIn("books/", str(file0))


class BookBrowseFiltersAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="testuser", password="testpass")

        self.author_a = Author.objects.create(name="Alice Author")
        self.author_b = Author.objects.create(name="Bob Writer")
        self.series_s = Series.objects.create(name="Saga Series")

        self.book1 = Book.objects.create(title="Alpha", language="en", series=self.series_s)
        self.book1.authors.add(self.author_a)
        ensure_book_public_assignment(book=self.book1, added_by=None)
        BookIdentifier.objects.create(book=self.book1, scheme="other", value="ID-XYZ", source="epub")

        self.book2 = Book.objects.create(title="Beta", language="fr")
        self.book2.authors.add(self.author_b)
        ensure_book_public_assignment(book=self.book2, added_by=None)

        uploaded = SimpleUploadedFile("ignored.epub", b"epub-bytes", content_type="application/epub+zip")
        BookFile.objects.create(
            book=self.book2,
            file=uploaded,
            checksum="b" * 64,
            file_size=9,
            source_filename="b.epub",
        )

    def _titles(self, response: Response):
        data = paginated_results(response)
        return sorted([b["title"] for b in data])

    def test_q_matches_title(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Alp"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_q_matches_author(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=bob"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Beta"])

    def test_q_matches_identifier_value(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?q=xyz"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_author(self):
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/books/?author={self.author_a.id}"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_series(self):
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/books/?series={self.series_s.id}"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_by_language(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?language=en"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Alpha"])

    def test_filter_has_files_true(self):
        response = cast(Response, self.client.get("/api/v1/library/books/?has_files=true"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self._titles(response), ["Beta"])
        data = paginated_results(response)
        files = data[0]["files"]
        self.assertEqual(len(files), 1)
        self.assertIn("download_url", files[0])
        self.assertNotIn("file", files[0])
        self.assertNotIn("books/", str(files[0]))


class PaginationBasicsAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.user)
        self.client.login(username="reader", password="pw")

        for i in range(51):
            book = Book.objects.create(title=f"Book {i:03d}")
            ensure_book_public_assignment(book=book, added_by=None)

    def test_books_list_is_paginated_with_standard_shape(self):
        response = cast(Response, self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        payload = cast(Mapping[str, Any], response.data)
        self.assertIn("count", payload)
        self.assertIn("next", payload)
        self.assertIn("previous", payload)
        self.assertIn("results", payload)

    def test_default_page_size_applies(self):
        response = cast(Response, self.client.get("/api/v1/library/books/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        self.assertEqual(payload["count"], 51)
        results = cast(list[Any], payload["results"])
        self.assertEqual(len(results), 50)

    def test_page_size_param_and_max_cap(self):
        r10 = cast(Response, self.client.get("/api/v1/library/books/?page_size=10"))
        self.assertEqual(r10.status_code, status.HTTP_200_OK)
        p10 = cast(Mapping[str, Any], r10.data)
        self.assertEqual(len(cast(list[Any], p10["results"])), 10)

        for i in range(51, 256):
            book = Book.objects.create(title=f"Book {i:03d}")
            ensure_book_public_assignment(book=book, added_by=None)

        rmax = cast(Response, self.client.get("/api/v1/library/books/?page_size=9999"))
        self.assertEqual(rmax.status_code, status.HTTP_200_OK)
        pmax = cast(Mapping[str, Any], rmax.data)
        self.assertEqual(pmax["count"], 256)
        self.assertEqual(len(cast(list[Any], pmax["results"])), 200)


class LibraryPermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

    def test_reader_cannot_create_book(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.post(
                "/api/v1/library/books/",
                data={"title": "X", "authors": [], "subjects": []},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_book(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.post(
                "/api/v1/library/books/",
                data={"title": "X", "authors": [], "subjects": []},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)


class LibraryVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        librarian_profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        librarian_profile.role = UserProfile.ROLE_LIBRARIAN
        librarian_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(username="manager", password="pw")
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.owner = User.objects.create_superuser(username="owner", password="pw", email="example@example.com")
        ensure_user_public_membership(user=self.owner)

        from library.models import LibraryGroup, LibraryGroupMembership
        from library.group_services import get_public_group

        self.public = get_public_group()
        self.group_a = LibraryGroup.objects.create(name="Group A", slug="group-a")
        self.group_b = LibraryGroup.objects.create(name="Group B", slug="group-b")

        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group_a, role=LibraryGroupMembership.ROLE_READER
        )

        self.public_book = Book.objects.create(title="Public Book")
        ensure_book_public_assignment(book=self.public_book, added_by=None)

        self.group_a_book = Book.objects.create(title="Group A Book")
        BookGroupAssignment.objects.create(book=self.group_a_book, group=self.group_a)

        self.group_b_book = Book.objects.create(title="Group B Book")
        BookGroupAssignment.objects.create(book=self.group_b_book, group=self.group_b)

        uploaded = SimpleUploadedFile("b.epub", b"epub-bytes", content_type="application/epub+zip")
        self.group_b_file = BookFile.objects.create(
            book=self.group_b_book,
            file=uploaded,
            checksum="c" * 64,
            file_size=9,
            source_filename="c.epub",
        )

    def test_reader_can_list_public_books(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Public"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in paginated_results(response)]
        self.assertIn("Public Book", titles)

    def test_reader_can_list_books_in_group_they_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Group A"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in paginated_results(response)]
        self.assertIn("Group A Book", titles)

    def test_reader_cannot_list_books_in_group_they_do_not_belong_to(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get("/api/v1/library/books/?q=Group B"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        titles = [b["title"] for b in paginated_results(response)]
        self.assertNotIn("Group B Book", titles)

    def test_reader_cannot_retrieve_inaccessible_book(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response, self.client.get(f"/api/v1/library/books/{self.group_b_book.id}/")
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reader_cannot_download_inaccessible_book_file(self):
        self.client.login(username="reader", password="pw")
        response = self.client.get(
            f"/api/v1/library/book-files/{self.group_b_file.id}/download/"
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_librarian_manager_owner_can_see_all_books(self):
        for username in ["librarian", "manager", "owner"]:
            self.client.logout()
            self.client.login(username=username, password="pw")
            response = cast(Response, self.client.get("/api/v1/library/books/"))
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            titles = sorted([b["title"] for b in paginated_results(response)])
            self.assertEqual(titles, ["Group A Book", "Group B Book", "Public Book"])


class AuthorSeriesVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)
        self.client.login(username="reader", password="pw")

        from library.models import LibraryGroup, LibraryGroupMembership

        self.group_x = LibraryGroup.objects.create(name="X", slug="x")
        LibraryGroupMembership.objects.create(
            user=self.reader, group=self.group_x, role=LibraryGroupMembership.ROLE_READER
        )
        self.group_y = LibraryGroup.objects.create(name="Y", slug="y")

        self.author_public = Author.objects.create(name="Public Author")
        self.series_public = Series.objects.create(name="Public Series")
        self.book_public = Book.objects.create(title="PB", series=self.series_public)
        self.book_public.authors.add(self.author_public)
        ensure_book_public_assignment(book=self.book_public, added_by=None)

        self.author_x = Author.objects.create(name="X Author")
        self.series_x = Series.objects.create(name="X Series")
        self.book_x = Book.objects.create(title="XB", series=self.series_x)
        self.book_x.authors.add(self.author_x)
        BookGroupAssignment.objects.create(book=self.book_x, group=self.group_x)

        self.author_hidden = Author.objects.create(name="Hidden Author")
        self.series_hidden = Series.objects.create(name="Hidden Series")
        self.book_hidden = Book.objects.create(title="HB", series=self.series_hidden)
        self.book_hidden.authors.add(self.author_hidden)
        BookGroupAssignment.objects.create(book=self.book_hidden, group=self.group_y)

    def test_reader_author_list_filtered(self):
        response = cast(Response, self.client.get("/api/v1/library/authors/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([a["name"] for a in paginated_results(response)])
        self.assertEqual(names, ["Public Author", "X Author"])

    def test_reader_author_retrieve_404_for_inaccessible_only(self):
        response = self.client.get(f"/api/v1/library/authors/{self.author_hidden.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_reader_series_list_filtered(self):
        response = cast(Response, self.client.get("/api/v1/library/series/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        names = sorted([s["name"] for s in paginated_results(response)])
        self.assertEqual(names, ["Public Series", "X Series"])

    def test_reader_series_retrieve_404_for_inaccessible_only(self):
        response = self.client.get(f"/api/v1/library/series/{self.series_hidden.id}/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BaseBookFileDownloadAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        profile, _ = UserProfile.objects.get_or_create(user=self.user)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])
        self.client.login(username="testuser", password="testpass")

        self.author = Author.objects.create(name="Test Author")
        self.book = Book.objects.create(title="Test Title")
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.book_file = BookFile.objects.create(
            book=self.book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="source.epub",
        )

    def test_download_requires_existing_file(self):
        response = cast(
            Response,
            self.client.get(
                f"/api/v1/library/book-files/{self.book_file.id}/download/"
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class BookFileSerializerAPITest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="testpass")
        ensure_user_public_membership(user=self.user)
        self.author = Author.objects.create(name="Test Author")
        self.book = Book.objects.create(title="Test Title")
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)
        self.book_file = BookFile.objects.create(
            book=self.book,
            file="books/aa/aa/aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa.epub",
            checksum="a" * 64,
            file_size=123,
            source_filename="source.epub",
        )

    def test_book_file_api_output_hides_file_and_includes_download_url(self):
        self.client.login(username="testuser", password="testpass")
        response = cast(
            Response,
            self.client.get(f"/api/v1/library/book-files/{self.book_file.id}/"),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        data = cast(Mapping[str, Any], response.data)
        self.assertNotIn("file", data)
        self.assertIn("download_url", data)
        self.assertEqual(
            data["download_url"],
            f"http://testserver/api/v1/library/book-files/{self.book_file.id}/download/",
        )


class BookFileDownloadAPITest(BaseBookFileDownloadAPITest):
    pass
