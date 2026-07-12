from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from playwright.sync_api import Page, expect


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
