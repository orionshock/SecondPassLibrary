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


class CatalogTagProductUiContractTests:
    def test_library_list_renders_current_nested_tag_names(self):
        source = (ROOT / "web/static/web/js/library/list.js").read_text(encoding="utf-8")

        assert "function renderTags(tags)" in source
        assert "tag && tag.name" in source
        assert "renderTags(b.tags)" in source
        assert "b.subjects" not in source

    def test_book_edit_uses_shared_uncapped_pagination_for_tags(self):
        source = (ROOT / "web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        shared = (ROOT / "web/static/web/js/book_edit/shared.js").read_text(encoding="utf-8")

        assert "fetchAllPaginatedResults" in source
        assert 'fetchAllPaginatedResults("/api/v1/library/tags/")' in source
        assert "fetchAllPages" not in source
        assert "fetchAllPages" not in shared
        assert "< 50" not in source
        assert "< 50" not in shared

        count = _run_node(
            """
            import { fetchAllPaginatedResults } from "./web/static/web/js/api.js";
            globalThis.fetch = async (url) => {
              const page = Number(String(url).replace("page-", ""));
              return {
                ok: true,
                status: 200,
                headers: { get: () => "application/json" },
                json: async () => ({
                  results: [{ id: page }],
                  next: page === 54 ? null : `page-${page + 1}`,
                }),
                text: async () => "",
              };
            };
            const results = await fetchAllPaginatedResults("page-0");
            process.stdout.write(JSON.stringify(results.length));
            """
        )
        assert count == 55

    def test_bad_continuations_have_a_bounded_visible_failure(self):
        source = (ROOT / "web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        template = (ROOT / "web/templates/web/library/book_edit.html").read_text(encoding="utf-8")

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
        assert 'id="book-edit-catalog-tags-status"' in template
        assert 'setStatus(catalogTagsStatusEl, "Failed to load Catalog Tags.", true)' in source
        assert 'console.error("Failed to load Catalog Tags", e)' in source
        assert len("Failed to load Catalog Tags.") < 80

    def test_book_patch_still_submits_tag_names(self):
        source = (ROOT / "web/static/web/js/book_edit/metadata.js").read_text(encoding="utf-8")

        assert "catalog_tags: catalogTags.map" in source
        assert "String(tag.name || \"\").trim()" in source
