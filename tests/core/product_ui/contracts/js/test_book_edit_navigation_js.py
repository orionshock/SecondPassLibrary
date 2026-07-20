from __future__ import annotations

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_book_edit_query_values_and_href_preserve_unrelated_params():
    result = run_node_json(
        """
        globalThis.window = { location: { origin: "https://example.test", search: "" } };
        const navigation = await import("./web/static/web/js/book_edit/navigation.js");
        process.stdout.write(JSON.stringify({
          catalog: navigation.bookEditTabFromSearch("?tab=catalog"),
          authors: navigation.bookEditTabFromSearch("?tab=authors-series"),
          unknown: navigation.bookEditTabFromSearch("?tab=bogus"),
          preserved: navigation.bookEditHref(
            "identifiers-file",
            "https://example.test/library/books/1/edit/?from=library&tab=book"
          ),
        }));
        """
    )

    assert result == {
        "catalog": "catalog",
        "authors": "authors-series",
        "unknown": "book",
        "preserved": "/library/books/1/edit/?from=library&tab=identifiers-file",
    }


def test_unavailable_groups_and_unknown_tabs_select_book_details():
    result = run_node_json(
        """
        globalThis.window = { location: { origin: "https://example.test", search: "" } };
        const { selectBookEditTab } = await import("./web/static/web/js/book_edit/navigation.js");
        function node(key, kind) {
          const classes = new Set();
          return {
            key,
            attributes: {},
            classList: { toggle(name, on) { if (on) classes.add(name); else classes.delete(name); } },
            getAttribute(name) { return name === kind ? key : this.attributes[name] || null; },
            setAttribute(name, value) { this.attributes[name] = value; },
          };
        }
        const buttons = [node("book-details", "data-tab"), node("catalog", "data-tab")];
        const panels = [node("book-details", "data-tab-panel"), node("catalog", "data-tab-panel")];
        const root = {
          querySelector(selector) {
            const match = selector.match(/data-tab="([^"]+)"/);
            return match ? buttons.find((button) => button.key === match[1]) || null : null;
          },
          querySelectorAll(selector) { return selector.includes("data-tab-panel") ? panels : buttons; },
        };
        const groups = selectBookEditTab(root, "groups");
        const unknown = selectBookEditTab(root, "unknown");
        process.stdout.write(JSON.stringify({
          groups,
          unknown,
          selected: buttons.find((button) => button.attributes["aria-selected"] === "true").key,
          panelVisible: panels.find((panel) => panel.attributes["aria-hidden"] === "false").key,
        }));
        """
    )

    assert result == {
        "groups": "book",
        "unknown": "book",
        "selected": "book-details",
        "panelVisible": "book-details",
    }
