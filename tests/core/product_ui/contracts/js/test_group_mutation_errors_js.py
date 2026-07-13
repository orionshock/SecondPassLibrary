from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


ROOT = Path(__file__).resolve().parents[5]


def _run_node(script: str):
    completed = subprocess.run(
        [
            "node",
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


class GroupMutationErrorsJavaScriptTests:
    def test_formatter_preserves_safe_structured_errors_and_bounds_fields(self):
        result = _run_node(
            """
            import { groupMutationErrorMessage } from "./web/static/web/js/groups/shared.js";

            const fieldMessage = groupMutationErrorMessage({
              body: {
                name: ["This field is required."],
                description: ["x".repeat(400)],
              },
              status: 400,
            }, "Failed to create group.");
            const envelopeMessage = groupMutationErrorMessage({
              body: { error: { code: "GROUP_DENIED", message: "Not allowed." } },
              status: 403,
            }, "Failed to save group description.");
            const detailMessage = groupMutationErrorMessage({
              body: { detail: "Permission denied." },
              status: 403,
            }, "Failed to save group description.");

            process.stdout.write(JSON.stringify({
              fieldMessage,
              fieldLength: fieldMessage.length,
              envelopeMessage,
              detailMessage,
            }));
            """
        )

        assert result["fieldMessage"].startswith("name: This field is required.")
        assert result["fieldLength"] <= 240
        assert result["envelopeMessage"] == "GROUP_DENIED: Not allowed."
        assert result["detailMessage"] == "Permission denied."

    def test_formatter_never_displays_raw_html_or_non_json_bodies(self):
        result = _run_node(
            """
            import { groupMutationErrorMessage } from "./web/static/web/js/groups/shared.js";

            const htmlBody = "<!doctype html><html><body>Proxy failure</body></html>";
            const nonJson = groupMutationErrorMessage({
              body: htmlBody,
              message: `Request failed (502): ${htmlBody}`,
              status: 502,
            }, "Failed to add book to group.");
            const jsonHtml = groupMutationErrorMessage({
              body: { detail: "<html><body>CSRF failure</body></html>" },
              status: 403,
            }, "Failed to remove book from group.");
            const traceback = groupMutationErrorMessage({
              body: { detail: 'Traceback (most recent call last): File "views.py", line 42' },
              status: 500,
            }, "Failed to save group description.");
            process.stdout.write(JSON.stringify({ nonJson, jsonHtml, traceback }));
            """
        )

        assert result == {
            "nonJson": "Failed to add book to group. (HTTP 502).",
            "jsonHtml": "Failed to remove book from group. (HTTP 403).",
            "traceback": "Failed to save group description. (HTTP 500).",
        }
        assert "<" not in result["nonJson"]
        assert "<" not in result["jsonHtml"]

    def test_all_group_mutations_use_the_same_safe_formatter(self):
        sources = {
            name: (ROOT / path).read_text(encoding="utf-8")
            for name, path in {
                "create": "web/static/web/js/groups/new.js",
                "description": "web/static/web/js/groups/edit.js",
                "books": "web/static/web/js/groups/books.js",
            }.items()
        }

        for source in sources.values():
            assert "groupMutationErrorMessage" in source
        assert 'groupMutationErrorMessage(err, "Failed to create group.")' in sources[
            "create"
        ]
        assert "Failed to save group description." in sources["description"]
        assert "Failed to add book to group." in sources["books"]
        assert "Failed to remove book from group." in sources["books"]
        assert "groupBookMutationError" not in sources["books"]

    def test_successful_mutation_contracts_remain_unchanged(self):
        new_js = (ROOT / "web/static/web/js/groups/new.js").read_text(encoding="utf-8")
        edit_js = (ROOT / "web/static/web/js/groups/edit.js").read_text(
            encoding="utf-8"
        )
        books_js = (ROOT / "web/static/web/js/groups/books.js").read_text(
            encoding="utf-8"
        )

        assert 'method: "POST"' in new_js
        assert "window.location.href" in new_js
        assert 'method: "PATCH"' in edit_js
        assert 'setStatus(saveStatus, "Saved.", false)' in edit_js
        assert "JSON.stringify({ book_id: bookId })" in books_js
        assert 'setBookSearchStatus("Added.", false)' in books_js
        assert "await booksCtl.reloadFirstPage()" in books_js
