from __future__ import annotations

from pathlib import Path

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_shelf_scope_urls_restore_supported_state_and_drop_unknown_params():
    result = run_node_json(
        r"""
        import {
          shelfListApiUrl,
          shelfListBrowserHref,
          shelfListState,
        } from "./web/static/web/js/shelves/list.js";

        const direct = shelfListState("?scope=group&page=4&page_size=40&keep=yes");
        process.stdout.write(JSON.stringify({
          direct,
          fallback: shelfListState("?scope=invalid&page=nope"),
          restored: shelfListBrowserHref(direct.scope, direct.page, direct.pageSize),
          switched: shelfListBrowserHref("shared", 1, direct.pageSize),
          resized: shelfListBrowserHref("group", 1, 50),
          api: shelfListApiUrl("group", 3, 40),
        }));
        """
    )

    assert result == {
        "direct": {"scope": "group", "page": 4, "pageSize": 40},
        "fallback": {"scope": "personal", "page": 1, "pageSize": 20},
        "restored": "/shelves/?scope=group&page=4&page_size=40",
        "switched": "/shelves/?scope=shared&page_size=40",
        "resized": "/shelves/?scope=group&page_size=50",
        "api": (
            "/api/v1/shelves/?scope=group&include_preview_books=true"
            "&page_size=40&page=3"
        ),
    }


def test_shelf_page_size_change_resets_page_before_history_navigation():
    source = Path("web/static/web/js/shelves/list.js").read_text(encoding="utf-8")

    assert "page: 1, pageSize: nextPageSize" in source
    assert 'history: "push", reason: "page-size"' in source
    assert 'window.addEventListener("popstate"' in source


def test_shelf_scope_empty_states_are_specific():
    result = run_node_json(
        r"""
        import { shelfEmptyText } from "./web/static/web/js/shelves/list.js";
        process.stdout.write(JSON.stringify({
          personal: shelfEmptyText("personal"),
          shared: shelfEmptyText("shared"),
          group: shelfEmptyText("group"),
        }));
        """
    )

    assert result == {
        "personal": "No personal shelves.",
        "shared": "No shared shelves from other users.",
        "group": "No group shelves.",
    }
