from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import UserProfile
from library.models import Author, BookAuthor
from tests.library.helpers import (
    LibraryCatalogApiFixtureMixin,
    assert_axis_detail_ignores_list_params,
    create_catalog_book,
    response_book_counts,
    response_names,
)
from tests.utils.users import set_user_role


def preview_titles(row):
    return [book["title"] for book in row["preview_books"]]


class LibraryAuthorAxisTests(LibraryCatalogApiFixtureMixin, TestCase):
    def test_librarian_manager_and_owner_can_create_author(self):
        User = get_user_model()
        librarian = User.objects.create_user(username="librarian", password="pw")
        set_user_role(librarian, UserProfile.ROLE_LIBRARIAN)
        User.objects.create_superuser(username="owner", password="pw")

        for username in ("librarian", "manager", "owner"):
            with self.subTest(username=username):
                self.client.logout()
                self.assertTrue(self.client.login(username=username, password="pw"))
                response = self.client.post(
                    "/api/v1/library/authors/",
                    data={"name": f"{username} Writer"},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(
                    set(response.json()),
                    {"id", "name", "sort_name", "biography", "book_count"},
                )
                self.assertEqual(response.json()["book_count"], 0)

    def test_create_author_accepts_sort_name_and_does_not_assign_a_book(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.post(
            "/api/v1/library/authors/",
            data={"name": "New Writer", "sort_name": "Writer, New"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 201)
        author = Author.objects.get(name="New Writer")
        self.assertEqual(author.sort_name, "Writer, New")
        self.assertFalse(BookAuthor.objects.filter(author=author).exists())

    def test_duplicate_author_names_are_allowed(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        for _ in range(2):
            response = self.client.post(
                "/api/v1/library/authors/",
                data={"name": "Deliberate Duplicate"},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 201)

        self.assertEqual(Author.objects.filter(name="Deliberate Duplicate").count(), 2)
        normalized = Author.objects.filter(name="Deliberate Duplicate").values_list(
            "normalized_name", flat=True
        )
        self.assertEqual(set(normalized), {"deliberate duplicate"})

    def test_manager_default_reads_include_full_catalog_and_total_counts(self):
        unattached = Author.objects.create(
            name="Unattached", sort_name="Unattached", normalized_name="unattached"
        )
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book(
            "Hidden Only Book",
            author=hidden_only,
            group=self.hidden,
            tag=self.fantasy,
        )
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        listed = self.client.get("/api/v1/library/authors/")
        detail = self.client.get(f"/api/v1/library/authors/{unattached.id}/")

        self.assertIn("Unattached", response_names(listed))
        self.assertIn("Hidden Only", response_names(listed))
        self.assertEqual(response_book_counts(listed)["Alpha Author"], 3)
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["book_count"], 0)

    def test_manager_tag_search_ordering_and_previews_use_full_book_scope(self):
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book(
            "Hidden Only Book",
            author=hidden_only,
            group=self.hidden,
            tag=self.fantasy,
        )
        hidden_prolific = Author.objects.create(
            name="Hidden Prolific", sort_name="Hidden Prolific"
        )
        for title in ("Hidden Prolific One", "Hidden Prolific Two"):
            create_catalog_book(
                title,
                author=hidden_prolific,
                group=self.hidden,
                tag=self.fantasy,
            )
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        filtered = self.client.get(
            "/api/v1/library/authors/",
            {"tag": self.fantasy.slug, "q": "hidden", "ordering": "-book_count"},
        )
        previews = self.client.get(
            "/api/v1/library/authors/",
            {"q": "alpha", "include_preview_books": "true"},
        )

        self.assertEqual(response_names(filtered), ["Hidden Prolific", "Hidden Only"])
        self.assertEqual(
            response_book_counts(filtered),
            {"Hidden Prolific": 2, "Hidden Only": 1},
        )
        self.assertIn("Hidden Dresden", preview_titles(previews.json()["results"][0]))

    def test_safe_delete_author(self):
        unattached = Author.objects.create(
            name="Disposable", sort_name="Disposable", normalized_name="disposable"
        )
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        deleted = self.client.delete(f"/api/v1/library/authors/{unattached.id}/")
        blocked = self.client.delete(f"/api/v1/library/authors/{self.alpha.id}/")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(blocked.json()["error"]["code"], "AUTHOR_IN_USE")

    def test_blank_and_overlong_author_names_are_rejected(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        for name in ("   ", "x" * 256):
            with self.subTest(length=len(name)):
                response = self.client.post(
                    "/api/v1/library/authors/",
                    data={"name": name},
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("name", response.json())

    def test_anonymous_cannot_create_author(self):
        self.client.logout()
        response = self.client.post(
            "/api/v1/library/authors/",
            data={"name": "Anonymous Writer"},
            content_type="application/json",
        )

        self.assertIn(response.status_code, {401, 403})
        self.assertFalse(Author.objects.filter(name="Anonymous Writer").exists())

    def test_reader_cannot_create_author(self):
        response = self.client.post(
            "/api/v1/library/authors/",
            data={"name": "Forbidden Writer"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.assertFalse(Author.objects.filter(name="Forbidden Writer").exists())

    def test_list_includes_only_authors_with_visible_books(self):
        Author.objects.create(name="Unattached", sort_name="Unattached")
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book("Hidden Only Book", author=hidden_only, group=self.hidden)

        response = self.client.get("/api/v1/library/authors/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Alpha Author", "Beta Author", "Zeta Author"])

    def test_book_count_counts_visible_books_only(self):
        self.alpha.biography = "Biography in list payload."
        self.alpha.save(update_fields=["biography", "updated_at"])
        response = self.client.get("/api/v1/library/authors/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response_book_counts(response),
            {"Alpha Author": 2, "Beta Author": 1, "Zeta Author": 1},
        )
        alpha = next(item for item in response.json()["results"] if item["name"] == "Alpha Author")
        self.assertEqual(alpha["biography"], "Biography in list payload.")

    def test_preview_books_are_opt_in_limited_and_visibility_scoped(self):
        for index in range(7):
            create_catalog_book(
                f"Alpha Preview {index:02d}",
                author=self.alpha,
                group=self.public,
            )

        default_response = self.client.get("/api/v1/library/authors/")
        preview_response = self.client.get(
            "/api/v1/library/authors/",
            {"include_preview_books": "true"},
        )
        detail_response = self.client.get(
            f"/api/v1/library/authors/{self.alpha.id}/",
            {"include_preview_books": "true"},
        )

        self.assertEqual(default_response.status_code, 200)
        self.assertNotIn("preview_books", default_response.json()["results"][0])
        self.assertEqual(preview_response.status_code, 200)
        alpha = next(
            row for row in preview_response.json()["results"] if row["name"] == "Alpha Author"
        )
        self.assertEqual(
            preview_titles(alpha),
            [f"Alpha Preview {index:02d}" for index in range(6)],
        )
        self.assertNotIn("Hidden Dresden", preview_titles(alpha))
        for preview in alpha["preview_books"]:
            self.assertEqual(set(preview), {"id", "title", "cover_url"})

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            preview_titles(detail_response.json()),
            [f"Alpha Preview {index:02d}" for index in range(6)],
        )

    def test_q_searches_name_and_sort_name(self):
        self.beta.sort_name = "Storm Writer"
        self.beta.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/authors/", {"q": "alpha"})
        by_sort_name = self.client.get("/api/v1/library/authors/", {"q": "storm"})

        self.assertEqual(response_names(by_name), ["Alpha Author"])
        self.assertEqual(response_names(by_sort_name), ["Beta Author"])

    def test_tag_slug_filters_authors_and_counts_tagged_visible_books(self):
        response = self.client.get(
            "/api/v1/library/authors/", {"tag": self.fantasy.slug}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Beta Author", "Zeta Author"])
        self.assertEqual(
            response_book_counts(response), {"Beta Author": 1, "Zeta Author": 1}
        )

    def test_unknown_tag_slug_returns_no_authors(self):
        response = self.client.get("/api/v1/library/authors/", {"tag": "missing"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), [])

    def test_ordering_name_and_book_count(self):
        cases = [
            ("name", ["Alpha Author", "Beta Author", "Zeta Author"]),
            ("-name", ["Zeta Author", "Beta Author", "Alpha Author"]),
            ("book_count", ["Beta Author", "Zeta Author", "Alpha Author"]),
            ("-book_count", ["Alpha Author", "Beta Author", "Zeta Author"]),
        ]

        for ordering, expected in cases:
            with self.subTest(ordering=ordering):
                response = self.client.get("/api/v1/library/authors/", {"ordering": ordering})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response_names(response), expected)

    def test_detail_visible_succeeds(self):
        self.alpha.biography = "An established catalog biography."
        self.alpha.save(update_fields=["biography", "updated_at"])
        response = self.client.get(f"/api/v1/library/authors/{self.alpha.id}/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Alpha Author")
        self.assertEqual(response.json()["book_count"], 2)
        self.assertEqual(response.json()["biography"], "An established catalog biography.")

    def test_librarian_can_patch_biography(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"name": "Updated Author Name", "biography": "Updated biography."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.name, "Updated Author Name")
        self.assertEqual(self.alpha.biography, "Updated biography.")
        self.assertEqual(self.alpha.normalized_name, "updated author name")
        self.assertEqual(response.json()["name"], "Updated Author Name")
        self.assertEqual(response.json()["biography"], "Updated biography.")

    def test_reader_cannot_patch_biography(self):
        response = self.client.patch(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"biography": "Forbidden biography."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.biography, "")

    def test_detail_ignores_list_only_params(self):
        assert_axis_detail_ignores_list_params(
            self,
            url=f"/api/v1/library/authors/{self.alpha.id}/",
            expected_name="Alpha Author",
        )

    def test_detail_with_no_visible_books_returns_404(self):
        unattached = Author.objects.create(name="Unattached", sort_name="Unattached")
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book("Hidden Only Book", author=hidden_only, group=self.hidden)

        for author in (unattached, hidden_only):
            with self.subTest(author=author.name):
                response = self.client.get(f"/api/v1/library/authors/{author.id}/")
                self.assertEqual(response.status_code, 404)

    def test_hidden_detail_returns_404_even_with_invalid_ordering(self):
        hidden_only = Author.objects.create(name="Hidden Only", sort_name="Hidden Only")
        create_catalog_book("Hidden Only Book", author=hidden_only, group=self.hidden)

        response = self.client.get(
            f"/api/v1/library/authors/{hidden_only.id}/",
            {"ordering": "created_at"},
        )

        self.assertEqual(response.status_code, 404)

    def test_invalid_ordering_returns_400(self):
        response = self.client.get("/api/v1/library/authors/", {"ordering": "created_at"})

        self.assertEqual(response.status_code, 400)

    def test_pagination_composes_with_ordering(self):
        response = self.client.get(
            "/api/v1/library/authors/",
            {"ordering": "-name", "page_size": 2},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_names(response), ["Zeta Author", "Beta Author"])
        self.assertIsNotNone(response.json()["next"])
