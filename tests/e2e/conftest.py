from __future__ import annotations

import os
from dataclasses import dataclass
from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from playwright.sync_api import Page, expect


E2E_OWNER_USERNAME = "browser-owner"
E2E_OWNER_PASSWORD = "browser-test-only-password"


@dataclass(frozen=True)
class E2EInstall:
    base_url: str
    owner_username: str


@pytest.fixture
def e2e_fixture_files() -> dict[str, Path]:
    root = Path(__file__).resolve().parents[2] / "TestFiles"
    return {
        "calibre_library": root / "CalibreLibrary.zip",
        "marginalia_verified": root / "SPL-Marginalia-Verified-Good.json",
        "marginalia_mixed": root / "SPL-Marginalia-Mixed-Unmatched-Broken-CFI-Test.json",
        "marginalia_unmatched": root / "second-pass-unmatched-marginalia.json",
    }


@pytest.fixture
def e2e_install(live_server, page: Page) -> E2EInstall:
    page.goto(f"{live_server.url}/setup/")
    expect(page.get_by_role("heading", name="Set up your library")).to_be_visible()

    page.get_by_label("Server Name").fill("Second Pass Browser Test Library")
    page.get_by_label("Server Description").fill(
        "Isolated Playwright development installation."
    )
    page.get_by_label("Public Group Name").fill("Common Room")
    page.get_by_label("Username").fill(E2E_OWNER_USERNAME)
    page.get_by_label("First name").fill("Browser")
    page.get_by_label("Last name").fill("Owner")
    page.get_by_label("Password", exact=True).fill(E2E_OWNER_PASSWORD)
    page.get_by_label("Confirm password").fill(E2E_OWNER_PASSWORD)
    page.get_by_role("button", name="Complete setup").click()

    expect(page.get_by_role("heading", name="Log in")).to_be_visible()
    page.get_by_label("Username").fill(E2E_OWNER_USERNAME)
    page.get_by_label("Password").fill(E2E_OWNER_PASSWORD)
    page.get_by_role("button", name="Log in").click()
    page.wait_for_url("**/dashboard/")
    expect(page.get_by_role("heading", name="My Shelves")).to_be_visible()

    call_command(
        "seed_dev_users",
        force=True,
        users=8,
        groups=2,
        verbosity=0,
        stdout=StringIO(),
    )
    page.reload()
    expect(page.get_by_role("heading", name="My Shelves")).to_be_visible()

    return E2EInstall(
        base_url=live_server.url,
        owner_username=E2E_OWNER_USERNAME,
    )


def pytest_configure(config: pytest.Config) -> None:
    if config.option.markexpr != "e2e":
        return

    # Playwright's synchronous fixture uses an asyncio-backed bridge. These
    # opt-in tests deliberately use Django's synchronous live-server APIs.
    os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "true")
