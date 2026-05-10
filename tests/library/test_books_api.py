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

        self.assertIn("file", book)
        self.assertIsInstance(book["file"], dict)
        file0 = cast(Mapping[str, Any], book["file"])
        self.assertIn("download_url", file0)
        self.assertNotIn("file", file0)
        self.assertNotIn("books/", str(file0))
        self.assertNotIn("files", book)


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
        file0 = data[0]["file"]
        self.assertIsNotNone(file0)
        self.assertIn("download_url", file0)
        self.assertNotIn("file", file0)
        self.assertNotIn("books/", str(file0))


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


class BookGroupsSummaryVisibilityAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        from library.group_services import get_public_group
        from library.models import LibraryGroup

        self.public = get_public_group()

        self.reader = User.objects.create_user(
            username="reader", email="reader@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.reader)
        reader_profile, _ = UserProfile.objects.get_or_create(user=self.reader)
        reader_profile.role = UserProfile.ROLE_READER
        reader_profile.save(update_fields=["role", "updated_at"])

        self.manager = User.objects.create_user(
            username="manager", email="manager@example.com", password="pw"
        )
        ensure_user_public_membership(user=self.manager)
        manager_profile, _ = UserProfile.objects.get_or_create(user=self.manager)
        manager_profile.role = UserProfile.ROLE_MANAGER
        manager_profile.save(update_fields=["role", "updated_at"])

        self.hidden_group = LibraryGroup.objects.create(
            name="Hidden",
            slug="hidden",
        )

        # Book is viewable via Public, but also assigned to an unlisted non-member group.
        self.book = Book.objects.create(title="Public+Hidden")
        ensure_book_public_assignment(book=self.book, added_by=None)
        BookGroupAssignment.objects.create(book=self.book, group=self.hidden_group)

    def test_manager_sees_all_assigned_groups(self):
        self.client.login(username="manager", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        groups = cast(list[dict[str, Any]], payload["groups"])
        slugs = {g["slug"] for g in groups}
        self.assertIn("public", slugs)
        self.assertIn("hidden", slugs)

    def test_reader_only_sees_viewable_groups(self):
        self.client.login(username="reader", password="pw")
        response = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        groups = cast(list[dict[str, Any]], payload["groups"])
        slugs = {g["slug"] for g in groups}
        self.assertIn("public", slugs)
        self.assertNotIn("hidden", slugs)


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


class BookPatchPermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.author = Author.objects.create(name="A Author")
        self.book = Book.objects.create(title="Original title", language="en")
        self.book.authors.add(self.author)
        ensure_book_public_assignment(book=self.book, added_by=None)

        self.reader = User.objects.create_user(username="reader", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.librarian = User.objects.create_user(username="librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

    def test_reader_cannot_patch_book_metadata(self):
        self.client.login(username="reader", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"title": "Nope"},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_patch_basic_book_metadata(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={
                    "title": "Updated title",
                    "publisher": "Pub",
                    "published_date": "2018-01-23",
                    "subjects": ["A", "B"],
                    "series_index": 2,
                },
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data)
        data = cast(Mapping[str, Any], response.data)
        self.assertEqual(data["title"], "Updated title")
        self.assertEqual(data["publisher"], "Pub")
        self.assertEqual(data["published_date"], "2018-01-23")
        self.assertEqual(data["subjects"], ["A", "B"])
        self.assertEqual(data["series_index"], "2.0")

    def test_librarian_can_patch_blank_subtitle(self):
        self.client.login(username="librarian", password="pw")
        response = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"subtitle": ""},
                format="json",
            ),
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], response.data)
        self.assertEqual(payload["subtitle"], "")

    def test_series_index_accepts_integer_or_one_decimal_and_rejects_invalid(self):
        self.client.login(username="librarian", password="pw")

        r1 = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": 5},
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], r1.data)["series_index"], "5.0")

        r2 = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": "5.1"},
                format="json",
            ),
        )
        self.assertEqual(r2.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], r2.data)["series_index"], "5.1")

        r3 = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": None},
                format="json",
            ),
        )
        self.assertEqual(r3.status_code, status.HTTP_200_OK)
        self.assertIsNone(cast(Mapping[str, Any], r3.data)["series_index"])

        r4 = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": "5.12"},
                format="json",
            ),
        )
        self.assertEqual(r4.status_code, status.HTTP_400_BAD_REQUEST)

        r5 = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/",
                data={"series_index": -1},
                format="json",
            ),
        )
        self.assertEqual(r5.status_code, status.HTTP_400_BAD_REQUEST)


class AuthorSeriesCreatePermissionsAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="reader2", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.librarian = User.objects.create_user(username="librarian2", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

    def test_reader_cannot_create_author_or_series(self):
        self.client.login(username="reader2", password="pw")
        r1 = cast(Response, self.client.post("/api/v1/library/authors/", data={"name": "Nope"}, format="json"))
        r2 = cast(Response, self.client.post("/api/v1/library/series/", data={"name": "Nope"}, format="json"))
        self.assertEqual(r1.status_code, status.HTTP_403_FORBIDDEN)
        self.assertEqual(r2.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_author_and_series(self):
        self.client.login(username="librarian2", password="pw")
        r1 = cast(Response, self.client.post("/api/v1/library/authors/", data={"name": "New Author"}, format="json"))
        r2 = cast(Response, self.client.post("/api/v1/library/series/", data={"name": "New Series"}, format="json"))
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r2.status_code, status.HTTP_201_CREATED)
        self.assertIn("id", cast(Mapping[str, Any], r1.data))
        self.assertIn("id", cast(Mapping[str, Any], r2.data))

    def test_book_patch_accepts_authors_and_series_ids(self):
        self.client.login(username="librarian2", password="pw")
        author = cast(dict[str, Any], cast(Response, self.client.post("/api/v1/library/authors/", data={"name": "A"}, format="json")).data)
        series = cast(dict[str, Any], cast(Response, self.client.post("/api/v1/library/series/", data={"name": "S"}, format="json")).data)

        book = Book.objects.create(title="T")
        ensure_book_public_assignment(book=book, added_by=None)

        resp = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{book.id}/",
                data={"authors": [author["id"]], "series": series["id"], "series_index": 1},
                format="json",
            ),
        )
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], resp.data)
        self.assertEqual([a["id"] for a in payload["authors"]], [author["id"]])
        self.assertEqual(payload["series"]["id"], series["id"])


class BookIdentifierCrudAPITest(IsolatedMediaRootMixin, APITestCase):
    def setUp(self):
        self.reader = User.objects.create_user(username="ident_reader", password="pw")
        ensure_user_public_membership(user=self.reader)

        self.librarian = User.objects.create_user(username="ident_librarian", password="pw")
        ensure_user_public_membership(user=self.librarian)
        profile, _ = UserProfile.objects.get_or_create(user=self.librarian)
        profile.role = UserProfile.ROLE_LIBRARIAN
        profile.save(update_fields=["role", "updated_at"])

        self.book = Book.objects.create(title="Book With Idents")
        ensure_book_public_assignment(book=self.book, added_by=None)

    def test_book_payload_identifiers_include_id(self):
        BookIdentifier.objects.create(book=self.book, scheme=BookIdentifier.SCHEME_UUID, value="abc", source="manual")
        self.client.login(username="ident_reader", password="pw")
        resp = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/"))
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        payload = cast(Mapping[str, Any], resp.data)
        self.assertIsInstance(payload["identifiers"], list)
        self.assertIn("id", payload["identifiers"][0])

    def test_reader_can_list_identifiers_but_cannot_mutate(self):
        ident = BookIdentifier.objects.create(book=self.book, scheme=BookIdentifier.SCHEME_UUID, value="abc", source="manual")

        self.client.login(username="ident_reader", password="pw")
        r_list = cast(Response, self.client.get(f"/api/v1/library/books/{self.book.id}/identifiers/"))
        self.assertEqual(r_list.status_code, status.HTTP_200_OK)
        self.assertEqual(len(cast(list, r_list.data)), 1)

        r_create = cast(
            Response,
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={"scheme": "uuid", "value": "def", "source": "manual", "is_primary": False},
                format="json",
            ),
        )
        self.assertEqual(r_create.status_code, status.HTTP_403_FORBIDDEN)

        r_patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident.id}/",
                data={"source": "nope"},
                format="json",
            ),
        )
        self.assertEqual(r_patch.status_code, status.HTTP_403_FORBIDDEN)

        r_delete = cast(Response, self.client.delete(f"/api/v1/library/books/{self.book.id}/identifiers/{ident.id}/"))
        self.assertEqual(r_delete.status_code, status.HTTP_403_FORBIDDEN)

    def test_librarian_can_create_patch_delete_and_duplicates_return_400(self):
        self.client.login(username="ident_librarian", password="pw")

        r1 = cast(
            Response,
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={"scheme": "isbn_13", "value": "9780123456472", "source": "manual", "is_primary": True},
                format="json",
            ),
        )
        self.assertEqual(r1.status_code, status.HTTP_201_CREATED)
        ident_id = cast(Mapping[str, Any], r1.data)["id"]

        r_dup = cast(
            Response,
            self.client.post(
                f"/api/v1/library/books/{self.book.id}/identifiers/",
                data={"scheme": "isbn_13", "value": "9780123456472", "source": "manual", "is_primary": False},
                format="json",
            ),
        )
        self.assertEqual(r_dup.status_code, status.HTTP_400_BAD_REQUEST)

        r_patch = cast(
            Response,
            self.client.patch(
                f"/api/v1/library/books/{self.book.id}/identifiers/{ident_id}/",
                data={"source": "edited"},
                format="json",
            ),
        )
        self.assertEqual(r_patch.status_code, status.HTTP_200_OK)
        self.assertEqual(cast(Mapping[str, Any], r_patch.data)["source"], "edited")

        # Identifier edits should not automatically change Book.isbn
        self.book.refresh_from_db()
        self.assertEqual(self.book.isbn, "")

        r_delete = cast(Response, self.client.delete(f"/api/v1/library/books/{self.book.id}/identifiers/{ident_id}/"))
        self.assertEqual(r_delete.status_code, status.HTTP_204_NO_CONTENT)
