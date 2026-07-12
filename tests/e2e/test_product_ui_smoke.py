from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from library.imports.normalization import normalize_identifier
from library.models import Author, Book, BookAuthor, BookIdentifier, BookSeries, Series


pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


def test_browser_completes_setup_and_opens_seeded_install(
    page: Page,
    e2e_install,
) -> None:
    user_model = get_user_model()
    assert user_model.objects.filter(is_superuser=True, is_active=True).count() == 1
    assert user_model.objects.count() >= 9

    response = page.goto(f"{e2e_install.base_url}/shelves/")

    assert response is not None
    assert response.status == 200
    expect(page.get_by_role("heading", name="Shelves", exact=True)).to_be_visible()
    expect(page.get_by_role("heading", name="Personal Shelves")).to_be_visible()
    expect(page.get_by_role("heading", name="Shared Shelves")).to_be_visible()


def test_book_edit_persists_aggregate_edits_and_renders_owned_file(
    page: Page,
    e2e_install,
    e2e_fixture_files,
    isolated_runtime_paths,
) -> None:
    console_errors: list[str] = []
    page.route(
        "https://fonts.googleapis.com/**",
        lambda route: route.fulfill(status=200, content_type="text/css", body=""),
    )
    page.on(
        "console",
        lambda message: console_errors.append(message.text) if message.type == "error" else None,
    )
    page.goto(f"{e2e_install.base_url}/imports/")
    page.get_by_label("File").set_input_files(e2e_fixture_files["calibre_library_small"])
    page.get_by_role("button", name="Upload").click()
    expect(page.locator("#imports-upload-status")).to_have_text(
        "Import complete.", timeout=120_000
    )

    book = Book.objects.exclude(book_file="").order_by("id").first()
    assert book is not None
    book.title = "Browser File Contract"
    book.save(update_fields=["title", "updated_at"])
    BookAuthor.objects.filter(book=book).delete()
    BookSeries.objects.filter(book=book).delete()
    BookIdentifier.objects.filter(book=book).delete()

    original_author = Author.objects.create(name="Browser Original Author")
    added_author = Author.objects.create(name="Browser Added Author")
    existing_series = Series.objects.create(name="Browser Existing Series")
    BookAuthor.objects.create(book=book, author=original_author, position=0)
    other_book = Book.objects.exclude(pk=book.pk).exclude(book_file="").order_by("id").first()
    assert other_book is not None
    BookAuthor.objects.filter(book=other_book).delete()
    BookAuthor.objects.create(book=other_book, author=added_author, position=0)
    BookSeries.objects.create(book=book, series=existing_series, series_index="2.50")

    edited_identifier = normalize_identifier(scheme="doi", value="10.1000/browser-old")
    removed_identifier = normalize_identifier(scheme="oclc", value="123456")
    assert edited_identifier is not None
    assert removed_identifier is not None
    edited_row = BookIdentifier.objects.create(
        book=book,
        scheme=edited_identifier.scheme,
        value=edited_identifier.value,
        normalized_value=edited_identifier.normalized_value,
    )
    removed_row = BookIdentifier.objects.create(
        book=book,
        scheme=removed_identifier.scheme,
        value=removed_identifier.value,
        normalized_value=removed_identifier.normalized_value,
    )

    identifier_requests: list[str] = []
    book_patch_payloads: list[dict] = []

    def capture_request(request) -> None:
        if "/identifiers/" in request.url:
            identifier_requests.append(request.url)
        if request.method == "PATCH" and request.url.endswith(f"/books/{book.id}/"):
            book_patch_payloads.append(json.loads(request.post_data or "{}"))

    page.on("request", capture_request)

    page.goto(f"{e2e_install.base_url}/library/books/{book.id}/edit/")
    expect(page.get_by_role("heading", name="Browser File Contract")).to_be_visible()

    page.get_by_label("Title", exact=True).fill("Browser Edited Book")
    page.get_by_label("Description").fill("Description saved through the aggregate Book PATCH.")
    page.get_by_role("button", name="Authors & Series").click()
    page.get_by_label("Add existing").select_option(str(added_author.id))
    page.locator("#book-edit-author-add-btn").click()
    page.locator("#book-edit-series-select").select_option(str(existing_series.id))
    page.get_by_label("Series index").fill("3.5")

    page.get_by_role("button", name="Identifiers & File Info").click()
    expect(page.locator("#book-edit-file-info")).not_to_contain_text("No stored file.")
    expect(page.get_by_text("EPUB", exact=True).last).to_be_visible()
    expect(page.get_by_text("Checksum", exact=True)).to_be_visible()
    expect(page.get_by_text("Source filename", exact=True)).to_have_count(0)

    edited_identifier_row = page.locator(f'tr[data-ident-id="{edited_row.id}"]')
    edited_identifier_row.locator('[data-ident-field="value"]').fill("10.1000/browser-edited")
    edited_identifier_row.get_by_role("button", name="Save").click()
    page.locator(f'tr[data-ident-id="{removed_row.id}"]').get_by_role(
        "button", name="Delete"
    ).click()
    add_identifier_row = page.locator('tr[data-ident-id=""]')
    add_identifier_row.locator('[data-ident-field="scheme"]').select_option("asin")
    add_identifier_row.locator('[data-ident-field="value"]').fill("BROWSER-ASIN")
    add_identifier_row.get_by_role("button", name="Add").click()

    page.locator("#book-edit-save").click()
    expect(page.locator("#book-edit-saved")).to_be_visible()
    assert book_patch_payloads[-1]["identifiers"] == [
        {"scheme": "doi", "value": "10.1000/browser-edited"},
        {"scheme": "asin", "value": "BROWSER-ASIN"},
    ]

    page.reload()
    expect(page.get_by_label("Title", exact=True)).to_have_value("Browser Edited Book")
    expect(page.get_by_label("Description")).to_have_value(
        "Description saved through the aggregate Book PATCH."
    )
    page.get_by_role("button", name="Authors & Series").click()
    expect(page.locator("#book-edit-authors-selected")).to_contain_text("Browser Original Author")
    expect(page.locator("#book-edit-authors-selected")).to_contain_text("Browser Added Author")
    expect(page.locator("#book-edit-series-select")).to_have_value(str(existing_series.id))
    expect(page.get_by_label("Series index")).to_have_value("3.50")

    page.get_by_label("New series").fill("Browser Newly Created Series")
    page.get_by_label("Series index").fill("7.2")
    page.locator("#book-edit-save").click()
    expect(page.locator("#book-edit-saved")).to_be_visible()
    page.reload()
    expect(page.locator("#book-edit-header-series")).to_contain_text(
        "Browser Newly Created Series 7.20"
    )
    page.get_by_role("button", name="Authors & Series").click()
    expect(page.get_by_label("Series index")).to_have_value("7.20")

    page.get_by_role("button", name="Identifiers & File Info").click()
    identifier_values = page.locator(
        '#book-edit-identifiers [data-ident-field="value"]'
    ).evaluate_all("elements => elements.map((element) => element.value)")
    assert "10.1000/browser-edited" in identifier_values
    assert "BROWSER-ASIN" in identifier_values
    assert "123456" not in identifier_values
    expect(page.locator("#book-edit-file-info")).not_to_contain_text("No stored file.")
    expect(page.locator("#book-edit-error")).not_to_contain_text("<!DOCTYPE html>")
    assert identifier_requests == []
    assert console_errors == []

    patch_url = f"{e2e_install.base_url}/api/v1/library/books/{book.id}/"
    page.route(
        patch_url,
        lambda route: route.fulfill(
            status=500,
            content_type="text/html",
            body="<!DOCTYPE html><html><body>raw server failure</body></html>",
        ),
        times=1,
    )
    page.locator("#book-edit-save").click()
    expect(page.locator("#book-edit-error")).to_have_text("Failed to save book.")
    expect(page.locator("#book-edit-error")).not_to_contain_text("raw server failure")
