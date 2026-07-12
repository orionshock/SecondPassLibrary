from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect

from tests.utils.books import create_file_backed_book


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


def test_book_edit_uses_book_patch_state_and_renders_owned_file(
    page: Page,
    e2e_install,
    isolated_runtime_paths,
) -> None:
    file_backed = create_file_backed_book(
        title="Browser File Contract",
        source_filename="browser-file-contract.epub",
    )
    identifier_requests: list[str] = []
    page.on(
        "request",
        lambda request: identifier_requests.append(request.url)
        if "/identifiers/" in request.url
        else None,
    )

    page.goto(f"{e2e_install.base_url}/library/books/{file_backed.book.id}/edit/")
    expect(page.get_by_role("heading", name="Browser File Contract")).to_be_visible()
    page.get_by_role("button", name="Identifiers & File Info").click()

    expect(page.get_by_text("browser-file-contract.epub", exact=True)).to_be_visible()
    expect(page.get_by_text("EPUB", exact=True).last).to_be_visible()
    expect(page.locator("#book-edit-error")).not_to_contain_text("<!DOCTYPE html>")
    assert identifier_requests == []
