import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_group_book_page_url_preserves_filters_and_syncs_history():
    module_uri = (ROOT / "web/static/web/js/groups/book_pagination.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{
          location: {{
            origin: "http://example.test",
            href: "http://example.test/groups/group-1/?view=books&tag=fantasy&q=fire&ordering=title&page_size=10&page=3&extra=keep",
            search: "?view=books&tag=fantasy&q=fire&ordering=title&page_size=10&page=3&extra=keep",
          }},
          history: {{
            pushed: null,
            pushState(_state, _title, href) {{ this.pushed = href; }},
            replaceState() {{}},
          }},
        }};
        const mod = await import("{module_uri}");
        const apiUrl = mod.groupBooksApiUrl("group-1");
        mod.syncGroupBookPage("/api/v1/library/groups/group-1/books/?page=4");
        console.log(JSON.stringify({{ apiUrl, pushed: window.history.pushed }}));
        """
    )

    assert result["apiUrl"].endswith(
        "?q=fire&ordering=title&tag=fantasy&page_size=10&page=3"
    )
    assert result["pushed"] == (
        "/groups/group-1/?view=books&tag=fantasy&q=fire&ordering=title"
        "&page_size=10&page=4&extra=keep"
    )


def test_group_book_page_status_handles_subsequent_and_empty_pages():
    module_uri = (ROOT / "web/static/web/js/groups/book_pagination.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{ location: {{ origin: "http://example.test" }} }};
        const mod = await import("{module_uri}");
        console.log(JSON.stringify({{
          filled: mod.groupBookPageStatus({{ count: 23 }}, [{{}}, {{}}, {{}}], "/books/?page=3"),
          empty: mod.groupBookPageStatus({{ count: 20 }}, [], "/books/?page=3"),
        }}));
        """
    )

    assert result == {
        "filled": "Page 3. Showing 3 of 23.",
        "empty": "Page 3. No books.",
    }


def test_group_book_controllers_use_safe_shared_pagination_without_new_axes():
    helper = (ROOT / "web/static/web/js/ui/paged_list.js").read_text(encoding="utf-8")
    view = (ROOT / "web/static/web/js/groups/view.js").read_text(encoding="utf-8")
    navigation = (ROOT / "web/static/web/js/groups/navigation.js").read_text(
        encoding="utf-8"
    )

    assert "Invalid paginated response." in helper
    assert "pagination continuation repeated." in helper
    assert 'loadErrorText: "Unable to load group books."' in view
    assert "initGroupViewPager" in view
    assert "syncGroupViewPageUrl" in view
    assert 'window.addEventListener("popstate"' in view
    assert 'const GROUP_VIEW_TABS = new Set(["books", "members", "shelves"])' in navigation
    assert '"authors"' not in navigation.split("const GROUP_VIEW_TABS", 1)[1].split(";", 1)[0]
    assert '"series"' not in navigation.split("const GROUP_VIEW_TABS", 1)[1].split(";", 1)[0]
    assert '"tags"' not in navigation.split("const GROUP_VIEW_TABS", 1)[1].split(";", 1)[0]


def test_shared_pager_rejects_malformed_repeating_and_cross_origin_links():
    module_uri = (ROOT / "web/static/web/js/ui/paged_list.js").as_uri()
    result = run_node_json(
        f"""
        globalThis.window = {{ location: {{ origin: "http://example.test" }} }};
        const mod = await import("{module_uri}");
        const failures = [];
        for (const value of [42, "/books/?page=2", "https://other.test/books/?page=3"]) {{
          try {{
            mod.paginationContinuation(value, "/books/?page=2", "next");
          }} catch (error) {{
            failures.push(error.message);
          }}
        }}
        console.log(JSON.stringify({{ failures }}));
        """
    )

    assert result["failures"] == [
        "Invalid next pagination continuation.",
        "next pagination continuation repeated.",
        "Invalid next pagination continuation.",
    ]
