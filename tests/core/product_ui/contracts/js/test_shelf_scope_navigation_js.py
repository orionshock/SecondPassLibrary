from __future__ import annotations

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_shelf_scope_urls_restore_scope_and_page_and_reset_only_page():
    result = run_node_json(
        r"""
        import {
          shelfListApiUrl,
          shelfListBrowserHref,
          shelfListState,
        } from "./web/static/web/js/shelves/list.js";

        process.stdout.write(JSON.stringify({
          direct: shelfListState("?scope=group&page=4&keep=yes"),
          fallback: shelfListState("?scope=invalid&page=nope"),
          switched: shelfListBrowserHref("shared", 1, "?scope=personal&page=8&keep=yes"),
          paged: shelfListBrowserHref("group", 3, "?scope=shared&keep=yes"),
          api: shelfListApiUrl("group", 3),
        }));
        """
    )

    assert result == {
        "direct": {"scope": "group", "page": 4},
        "fallback": {"scope": "personal", "page": 1},
        "switched": "/shelves/?scope=shared&keep=yes",
        "paged": "/shelves/?scope=group&keep=yes&page=3",
        "api": "/api/v1/shelves/?scope=group&include_preview_books=true&page=3",
    }


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
