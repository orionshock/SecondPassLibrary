from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError
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

    def test_create_and_patch_reject_unknown_fields(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        created = self.client.post(
            "/api/v1/library/authors/",
            data={"name": "Rejected Writer", "book_count": 4, "random_field": True},
            content_type="application/json",
        )
        patched = self.client.patch(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"name": "Should Not Persist", "groups": []},
            content_type="application/json",
        )

        self.assertEqual(created.status_code, 400)
        self.assertEqual(
            created.json(),
            {"book_count": ["Unknown field."], "random_field": ["Unknown field."]},
        )
        self.assertFalse(Author.objects.filter(name="Rejected Writer").exists())
        self.assertEqual(patched.status_code, 400)
        self.assertEqual(patched.json(), {"groups": ["Unknown field."]})
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.name, "Alpha Author")

    def test_patch_sort_name_controls_ordering(self):
        first = Author.objects.create(name="Lifecycle Alpha", sort_name="Lifecycle Alpha")
        second = Author.objects.create(name="Lifecycle Beta", sort_name="Lifecycle Beta")
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.patch(
            f"/api/v1/library/authors/{first.id}/",
            data={"sort_name": "Zulu Lifecycle"},
            content_type="application/json",
        )
        ordered = self.client.get(
            "/api/v1/library/authors/", {"q": "lifecycle", "ordering": "name"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["sort_name"], "Zulu Lifecycle")
        self.assertEqual(response_names(ordered), [second.name, first.name])

    def test_patch_blank_sort_name_defaults_to_name_and_omission_preserves_it(self):
        self.alpha.sort_name = "Preserved Sort"
        self.alpha.save(update_fields=["sort_name", "updated_at"])
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        renamed = self.client.patch(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"name": "Renamed Author"},
            content_type="application/json",
        )
        blanked = self.client.patch(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"sort_name": ""},
            content_type="application/json",
        )

        self.assertEqual(renamed.json()["sort_name"], "Preserved Sort")
        self.assertEqual(blanked.json()["sort_name"], "Renamed Author")
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.sort_name, "Renamed Author")

    def test_put_is_not_supported(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        response = self.client.put(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"name": "Replacement"},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 405)

    def test_patch_model_validation_error_is_structured(self):
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        with patch(
            "library.catalog.axis_views.update_author",
            side_effect=DjangoValidationError({"name": ["Rejected by model."]}),
        ):
            response = self.client.patch(
                f"/api/v1/library/authors/{self.alpha.id}/",
                data={"name": "Valid Serializer Input"},
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {"name": ["Rejected by model."]})

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
        User = get_user_model()
        librarian = User.objects.create_user(username="delete-librarian", password="pw")
        set_user_role(librarian, UserProfile.ROLE_LIBRARIAN)
        self.client.logout()
        self.assertTrue(self.client.login(username="delete-librarian", password="pw"))

        deleted = self.client.delete(f"/api/v1/library/authors/{unattached.id}/")
        blocked = self.client.delete(f"/api/v1/library/authors/{self.alpha.id}/")

        self.assertEqual(deleted.status_code, 204)
        self.assertEqual(blocked.status_code, 409)
        self.assertEqual(
            blocked.json()["error"],
            {
                "code": "author_has_books",
                "message": "Author cannot be deleted because 3 Books are attached.",
                "details": {"book_count": 3},
            },
        )
        self.assertTrue(Author.objects.filter(pk=self.alpha.pk).exists())
        self.assertTrue(BookAuthor.objects.filter(author=self.alpha).exists())
        self.assertTrue(BookAuthor.objects.filter(author=self.alpha, book=self.visible_two).exists())

    def test_late_author_protection_failure_uses_the_same_bounded_conflict(self):
        unattached = Author.objects.create(name="Raced", sort_name="Raced")
        self.client.logout()
        self.assertTrue(self.client.login(username="manager", password="pw"))

        with patch.object(
            Author,
            "delete",
            side_effect=ProtectedError("protected", [object()]),
        ):
            response = self.client.delete(f"/api/v1/library/authors/{unattached.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["error"]["code"], "author_has_books")
        self.assertEqual(response.json()["error"]["details"], {"book_count": 1})
        self.assertTrue(Author.objects.filter(pk=unattached.pk).exists())

    def test_reader_cannot_delete_author(self):
        response = self.client.delete(f"/api/v1/library/authors/{self.alpha.id}/")
        missing = self.client.delete(f"/api/v1/library/authors/{uuid4()}/")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(missing.status_code, response.status_code)
        self.assertTrue(Author.objects.filter(pk=self.alpha.pk).exists())

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

    def test_preview_limit_is_bounded_explicit_and_does_not_change_book_count(self):
        limited = Author.objects.create(name="Limited Preview Author")
        for index in range(25):
            create_catalog_book(
                f"Limited Preview {index:02d}",
                author=limited,
                group=self.public,
            )

        default_response = self.client.get(
            "/api/v1/library/authors/", {"include_preview_books": "true"}
        )
        default_row = next(
            row for row in default_response.json()["results"] if row["id"] == str(limited.id)
        )
        self.assertEqual(len(default_row["preview_books"]), 6)
        self.assertEqual(default_row["book_count"], 25)

        for limit in (1, 6, 12, 24):
            with self.subTest(limit=limit):
                response = self.client.get(
                    "/api/v1/library/authors/", {"preview_limit": str(limit)}
                )
                row = next(
                    item for item in response.json()["results"] if item["id"] == str(limited.id)
                )
                self.assertEqual(len(row["preview_books"]), limit)
                self.assertEqual(row["book_count"], 25)
                self.assertEqual(
                    preview_titles(row),
                    [f"Limited Preview {index:02d}" for index in range(limit)],
                )

        disabled = self.client.get(
            "/api/v1/library/authors/",
            {"include_preview_books": "true", "preview_limit": "0"},
        )
        disabled_row = next(
            row for row in disabled.json()["results"] if row["id"] == str(limited.id)
        )
        self.assertNotIn("preview_books", disabled_row)
        self.assertEqual(disabled_row["book_count"], 25)

        invalid_queries = (
            "preview_limit=25",
            "preview_limit=-1",
            "preview_limit=not-a-number",
            "preview_limit=1.5",
            "preview_limit=1&preview_limit=2",
            "include_preview_books=false&preview_limit=1",
        )
        for query in invalid_queries:
            with self.subTest(query=query):
                response = self.client.get(f"/api/v1/library/authors/?{query}")
                self.assertEqual(response.status_code, 400)
                self.assertEqual(set(response.json()), {"preview_limit"})

    def test_q_searches_name_and_sort_name(self):
        self.beta.sort_name = "Storm Writer"
        self.beta.save(update_fields=["sort_name", "updated_at"])

        by_name = self.client.get("/api/v1/library/authors/", {"q": "alpha"})
        by_sort_name = self.client.get("/api/v1/library/authors/", {"q": "storm"})

        self.assertEqual(response_names(by_name), ["Alpha Author"])
        self.assertEqual(response_names(by_sort_name), ["Beta Author"])

    def test_q_normalizes_the_normalized_name_search_term(self):
        self.beta.normalized_name = "normalized author"
        self.beta.save(update_fields=["normalized_name", "updated_at"])

        response = self.client.get(
            "/api/v1/library/authors/", {"q": "  ＮORMALIZED   AUTHOR "}
        )

        self.assertEqual(response_names(response), ["Beta Author"])

    def test_search_can_exclude_one_author_id(self):
        response = self.client.get(
            "/api/v1/library/authors/",
            {"q": "author", "exclude_id": self.alpha.id, "page_size": 10},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(str(self.alpha.id), [row["id"] for row in response.json()["results"]])

        for query in ("exclude_id=invalid", f"exclude_id={self.alpha.id}&exclude_id={self.beta.id}"):
            with self.subTest(query=query):
                invalid = self.client.get(f"/api/v1/library/authors/?{query}")
                self.assertEqual(invalid.status_code, 400)
                self.assertEqual(set(invalid.json()), {"exclude_id"})

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
        author_id = self.alpha.id
        related_book_ids = set(
            BookAuthor.objects.filter(author=self.alpha).values_list("book_id", flat=True)
        )

        response = self.client.patch(
            f"/api/v1/library/authors/{self.alpha.id}/",
            data={"name": "Updated Author Name", "biography": "Updated biography."},
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.alpha.refresh_from_db()
        self.assertEqual(self.alpha.id, author_id)
        self.assertEqual(
            set(
                BookAuthor.objects.filter(author=self.alpha).values_list(
                    "book_id", flat=True
                )
            ),
            related_book_ids,
        )
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
