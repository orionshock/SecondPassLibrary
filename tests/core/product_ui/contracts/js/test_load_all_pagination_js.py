from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


ROOT = Path(__file__).resolve().parents[5]


def _run_node(script: str) -> dict:
    completed = subprocess.run(
        [
            "node",
            "--experimental-default-type=module",
            "--input-type=module",
            "--eval",
            script,
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(completed.stdout)


class TestLoadAllPaginationJavaScript:
    def test_shared_helper_follows_more_than_twenty_pages_and_normal_flows(self):
        result = _run_node(
            """
            import { fetchAllPaginatedResults } from "./web/static/web/js/api.js";

            const responses = new Map();
            for (let page = 0; page < 25; page += 1) {
              responses.set(`page-${page}`, {
                results: [{ id: page }],
                next: page === 24 ? null : `page-${page + 1}`,
              });
            }
            responses.set("one-page", { results: [{ id: "only" }], next: null });
            const calls = [];
            globalThis.fetch = async (url) => {
              calls.push(String(url));
              return {
                ok: true,
                headers: { get: () => "application/json" },
                json: async () => responses.get(String(url)),
                text: async () => "",
              };
            };

            const many = await fetchAllPaginatedResults("page-0");
            const one = await fetchAllPaginatedResults("one-page");
            process.stdout.write(JSON.stringify({
              manyCount: many.length,
              lastId: many.at(-1).id,
              oneCount: one.length,
              pageCalls: calls.filter((url) => url.startsWith("page-")).length,
            }));
            """
        )

        assert result == {
            "manyCount": 25,
            "lastId": 24,
            "oneCount": 1,
            "pageCalls": 25,
        }

    def test_shared_helper_rejects_repeating_and_malformed_continuations(self):
        result = _run_node(
            """
            import { fetchAllPaginatedResults } from "./web/static/web/js/api.js";

            const responses = new Map([
              ["repeat", { results: [], next: "repeat" }],
              ["malformed", { results: [], next: { page: 2 } }],
            ]);
            globalThis.fetch = async (url) => ({
              ok: true,
              headers: { get: () => "application/json" },
              json: async () => responses.get(String(url)),
              text: async () => "",
            });

            const errors = [];
            for (const url of ["repeat", "malformed"]) {
              try {
                await fetchAllPaginatedResults(url);
              } catch (error) {
                errors.push(error.message);
              }
            }
            process.stdout.write(JSON.stringify(errors));
            """
        )

        assert result == [
            "Pagination continuation repeated.",
            "Invalid pagination continuation.",
        ]

    def test_all_product_ui_collectors_use_the_shared_uncapped_helper(self):
        sources = {
            path: (ROOT / path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/groups/books.js",
                "web/static/web/js/shelves/new.js",
                "web/static/web/js/shelves/items.js",
                "web/static/web/js/users/memberships.js",
            )
        }
        for path, source in sources.items():
            assert "fetchAllPaginatedResults" in source, path
            assert "< 10" not in source, path
            assert "< 20" not in source, path
            assert "page_size=200" not in source, path
