from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


ROOT = Path(__file__).resolve().parents[5]


def _run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class LibrarySearchJavaScriptTests:
    def test_axis_urls_preserve_query_and_non_pagination_filters(self):
        result = _run_node(
            """
            import {
              canonicalLibraryParams,
              preservedLibraryParams,
            } from "./web/static/web/js/library/navigation.js";

            const source = new URLSearchParams(
              "view=authors&q=old&page=7&page_size=30&tag=tag-id&ordering=-name&publisher=Orbit&custom=value"
            );
            const preserved = preservedLibraryParams(source);
            const paramsFor = (view, q) => canonicalLibraryParams({
              view,
              q,
              page: 1,
              pageSize: 30,
              authorId: "",
              seriesId: "",
              preservedParams: preserved,
            }, { defaultPageSize: 20 });

            console.log(JSON.stringify({
              books: paramsFor("books", "dresden"),
              authors: paramsFor("authors", "butcher"),
              series: paramsFor("series", "files"),
              cleared: paramsFor("authors", ""),
            }));
            """
        )

        for view in ("books", "authors", "series"):
            params = result[view]
            assert params["view"] == view
            assert params["tag"] == "tag-id"
            assert params["ordering"] == "-name"
            assert params["publisher"] == "Orbit"
            assert params["custom"] == "value"
            assert params["page_size"] == 30
            assert "page" not in params

        assert result["books"]["q"] == "dresden"
        assert result["authors"]["q"] == "butcher"
        assert result["series"]["q"] == "files"
        assert "q" not in result["cleared"]
        assert result["cleared"]["view"] == "authors"

    def test_axis_placeholders(self):
        result = _run_node(
            """
            import { librarySearchPlaceholder } from "./web/static/web/js/library/navigation.js";
            console.log(JSON.stringify({
              books: librarySearchPlaceholder("books"),
              authors: librarySearchPlaceholder("authors"),
              series: librarySearchPlaceholder("series"),
              seriesBooks: librarySearchPlaceholder("series", "series-id"),
            }));
            """
        )

        assert result == {
            "books": "Title, author, series, identifier...",
            "authors": "Author name...",
            "series": "Series name...",
            "seriesBooks": "Title, author, series, identifier...",
        }

    def test_submit_and_history_restore_keep_the_active_axis(self):
        source = (ROOT / "web/static/web/js/library/list.js").read_text(encoding="utf-8")
        submit = source.split('form.addEventListener("submit"', 1)[1].split(
            'pageSizeSelect.addEventListener("change"', 1
        )[0]

        assert 'state.q = (qInput.value || "").trim()' in submit
        assert "state.page = 1" in submit
        assert 'state.view = "books"' not in submit
        assert "state.authorId" not in submit
        assert "state.seriesId" not in submit
        assert 'state.q = (params.get("q") || "").trim()' in source
        assert "state.preservedParams = preservedLibraryParams(params)" in source
        assert 'window.addEventListener("popstate"' in source
        assert "syncStateFromLocation();" in source
        assert "await loadCurrentPage();" in source

    def test_each_axis_api_receives_the_current_query(self):
        source = (ROOT / "web/static/web/js/library/list.js").read_text(encoding="utf-8")

        assert "const commonParams = {" in source
        assert "q: state.q" in source
        assert 'urlWithParams("/api/v1/library/books/"' in source
        assert 'urlWithParams("/api/v1/library/authors/"' in source
        assert 'urlWithParams("/api/v1/library/series/"' in source
        assert 'q: state.view === "books" ? state.q : ""' not in source

    def test_search_control_has_scoped_compact_layout(self):
        template = (ROOT / "web/templates/web/library/library.html").read_text(encoding="utf-8")
        css = (ROOT / "web/static/web/css/library.css").read_text(encoding="utf-8")

        assert 'class="search library-search"' in template
        assert 'placeholder="Title, author, series, identifier..."' in template
        assert ".library-search {" in css
        assert ".library-search .search__input {" in css
        assert "flex: 1 1 360px" in css
        assert "min-width: 140px" in css
        assert "flex-basis: 100%" in css
