from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


ROOT = Path(__file__).resolve().parents[5]


def _run_node(script: str):
    completed = subprocess.run(
        ["node", "--input-type=module", "--eval", script],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class CatalogTagRailJavaScriptTests:
    def test_options_use_server_names_counts_and_active_states(self):
        result = _run_node(
            """
            import { catalogTagOptions } from "./web/static/web/js/library/catalog_tags.js";
            const tags = [
              { name: "Fantasy", slug: "fantasy", book_count: 12 },
              { name: "Science Fiction", slug: "science-fiction", book_count: 4 },
            ];
            process.stdout.write(JSON.stringify({
              all: catalogTagOptions(tags, ""),
              active: catalogTagOptions(tags, "science-fiction"),
            }));
            """
        )

        assert result["all"][0] == {
            "slug": "",
            "name": "All tags",
            "bookCount": None,
            "active": True,
        }
        assert result["active"][0]["active"] is False
        assert result["active"][1]["name"] == "Fantasy"
        assert result["active"][1]["bookCount"] == 12
        assert result["active"][2] == {
            "slug": "science-fiction",
            "name": "Science Fiction",
            "bookCount": 4,
            "active": True,
        }

    def test_select_and_clear_preserve_url_state_and_reset_only_page(self):
        result = _run_node(
            """
            import {
              canonicalLibraryParams,
              libraryParamsForTagSelection,
              preservedLibraryParams,
            } from "./web/static/web/js/library/navigation.js";

            const current = new URLSearchParams(
              "view=authors&q=butcher&page=9&page_size=30&tag=old&ordering=-name&publisher=Orbit&custom=value"
            );
            const base = {
              view: "authors",
              q: "butcher",
              page: 1,
              pageSize: 30,
              authorId: "",
              seriesId: "",
            };
            const selected = libraryParamsForTagSelection(
              preservedLibraryParams(current), "science-fiction"
            );
            const cleared = libraryParamsForTagSelection(selected, "");
            process.stdout.write(JSON.stringify({
              selected: canonicalLibraryParams(
                { ...base, preservedParams: selected }, { defaultPageSize: 20 }
              ),
              cleared: canonicalLibraryParams(
                { ...base, preservedParams: cleared }, { defaultPageSize: 20 }
              ),
              selectedQuery: new URLSearchParams(canonicalLibraryParams(
                { ...base, preservedParams: selected }, { defaultPageSize: 20 }
              )).toString(),
            }));
            """
        )

        assert result["selected"] == {
            "tag": "science-fiction",
            "ordering": "-name",
            "publisher": "Orbit",
            "custom": "value",
            "view": "authors",
            "q": "butcher",
            "page_size": 30,
        }
        assert result["cleared"] == {
            "ordering": "-name",
            "publisher": "Orbit",
            "custom": "value",
            "view": "authors",
            "q": "butcher",
            "page_size": 30,
        }
        assert result["selectedQuery"].startswith(
            "view=authors&tag=science-fiction&q=butcher&"
        )

    def test_rail_uses_complete_loop_safe_tag_pagination(self):
        source = (ROOT / "web/static/web/js/library/catalog_tags.js").read_text(
            encoding="utf-8"
        )
        result = _run_node(
            """
            import { fetchAllPaginatedResults } from "./web/static/web/js/api.js";
            globalThis.fetch = async (url) => {
              const page = Number(String(url).replace("page-", ""));
              return {
                ok: true,
                status: 200,
                headers: { get: () => "application/json" },
                json: async () => ({
                  results: [{ slug: `tag-${page}` }],
                  next: page === 54 ? null : `page-${page + 1}`,
                }),
                text: async () => "",
              };
            };
            const tags = await fetchAllPaginatedResults("page-0");
            process.stdout.write(JSON.stringify({ count: tags.length, last: tags.at(-1).slug }));
            """
        )

        assert 'fetchAllPaginatedResults("/api/v1/library/tags/")' in source
        assert "page_size=200" not in source
        assert result == {"count": 55, "last": "tag-54"}

    def test_malformed_and_repeating_continuations_fail_safely(self):
        source = (ROOT / "web/static/web/js/library/catalog_tags.js").read_text(
            encoding="utf-8"
        )
        errors = _run_node(
            """
            import { fetchAllPaginatedResults } from "./web/static/web/js/api.js";
            const payloads = {
              repeat: { results: [], next: "repeat" },
              malformed: { results: [], next: { page: 2 } },
            };
            globalThis.fetch = async (url) => ({
              ok: true,
              status: 200,
              headers: { get: () => "application/json" },
              json: async () => payloads[url],
              text: async () => "",
            });
            const messages = [];
            for (const url of ["repeat", "malformed"]) {
              try {
                await fetchAllPaginatedResults(url);
              } catch (error) {
                messages.push(error.message);
              }
            }
            process.stdout.write(JSON.stringify(messages));
            """
        )

        assert errors == [
            "Pagination continuation repeated.",
            "Invalid pagination continuation.",
        ]
        assert 'error = "Unable to load Catalog Tags."' in source
        assert 'console.error("Failed to load Library Catalog Tags", cause)' in source
        assert len("Unable to load Catalog Tags.") < 80

    def test_controller_passes_active_slug_to_every_axis_and_restores_history(self):
        source = (ROOT / "web/static/web/js/library/list.js").read_text(encoding="utf-8")

        assert "...state.preservedParams" in source
        assert 'urlWithParams("/api/v1/library/books/"' in source
        assert 'urlWithParams("/api/v1/library/authors/"' in source
        assert 'urlWithParams("/api/v1/library/series/"' in source
        assert 'getActiveSlug: () => state.preservedParams.tag || ""' in source
        assert "libraryParamsForTagSelection(state.preservedParams, slug)" in source
        assert "state.page = 1" in source
        assert "state.preservedParams = preservedLibraryParams(params)" in source
        assert "if (tagFilter) tagFilter.sync()" in source
        assert 'window.addEventListener("popstate"' in source
        assert "syncStateFromLocation();" in source
        assert "await loadCurrentPage();" in source
        rail_source = (ROOT / "web/static/web/js/library/catalog_tags.js").read_text(
            encoding="utf-8"
        )
        assert 'slug && slug === getActiveSlug() ? "" : slug' in rail_source
        assert 'button.setAttribute("aria-pressed", option.active ? "true" : "false")' in rail_source
        assert 'button.type = "button"' in rail_source

    def test_responsive_rail_markup_exists_without_a_tags_axis(self):
        template = (ROOT / "web/templates/web/library/library.html").read_text(
            encoding="utf-8"
        )
        css = (ROOT / "web/static/web/css/library.css").read_text(encoding="utf-8")
        source = (ROOT / "web/static/web/js/library/list.js").read_text(encoding="utf-8")

        assert 'class="library-browse-layout"' in template
        assert 'class="library-tag-filter"' in template
        assert 'class="library-tag-filter__disclosure" open' in template
        assert "<summary>Catalog Tags</summary>" in template
        assert 'id="library-tag-filter-options"' in template
        assert ".library-browse-layout {" in css
        assert "grid-template-columns: minmax(150px, 190px) minmax(0, 1fr)" in css
        assert "@media (max-width: 720px)" in css
        assert "grid-template-columns: minmax(0, 1fr)" in css
        assert 'window.matchMedia("(max-width: 720px)")' in (
            ROOT / "web/static/web/js/library/catalog_tags.js"
        ).read_text(encoding="utf-8")
        assert 'data-view="tags"' not in template
        assert '"tags"' not in source.split("const TAB_VIEWS", 1)[1].split(";", 1)[0]
