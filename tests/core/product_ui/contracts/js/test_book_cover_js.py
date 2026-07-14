from __future__ import annotations

import json
from pathlib import Path
import subprocess

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


class BookCoverProductUiContractTests:
    def test_cover_action_is_librarian_gated_and_uses_narrow_endpoint(self):
        detail = (ROOT / "web/static/web/js/library/detail.js").read_text(encoding="utf-8")
        editor = (ROOT / "web/static/web/js/library/cover_editor.js").read_text(encoding="utf-8")
        template = (ROOT / "web/templates/web/library/book_detail.html").read_text(
            encoding="utf-8"
        )

        assert "const canManage = canManageLibrary(me)" in detail
        assert "visible(coverEditEl, canManage)" in detail
        assert "can_manage_library" in template
        assert 'id="book-cover-edit"' in template
        assert "new FormData()" in editor
        assert 'data.append("cover", file)' in editor
        assert 'method: "POST"' in editor
        assert 'method: "DELETE"' in editor
        assert "/api/v1/library/books/${encodeURIComponent(String(bookId))}/cover/" in editor
        assert '"Content-Type"' not in editor

    def test_preview_cancel_clear_and_bounded_states_are_present(self):
        editor = (ROOT / "web/static/web/js/library/cover_editor.js").read_text(encoding="utf-8")
        template = (ROOT / "web/templates/web/library/book_detail.html").read_text(
            encoding="utf-8"
        )

        assert 'id="book-cover-selection"' in template
        assert 'id="book-cover-preview"' in template
        assert "URL.createObjectURL(file)" in editor
        assert "URL.revokeObjectURL(previewUrl)" in editor
        assert 'cancelButton.addEventListener("click", close)' in editor
        assert 'window.confirm("Clear this cover?")' in editor
        assert 'setStatus(statusEl, "Cover updated.", false)' in editor
        assert 'setStatus(statusEl, "Cover cleared.", false)' in editor
        assert 'console.error("Failed to replace book cover"' in editor
        assert 'console.error("Failed to clear book cover"' in editor

        messages = _run_node(
            """
            import { coverMutationError } from "./web/static/web/js/library/cover_editor.js";
            const long = "x".repeat(400);
            const messages = [
              coverMutationError({ body: { cover: ["Bad image."] } }, "fallback"),
              coverMutationError({ body: { error: { message: "Denied." } } }, "fallback"),
              coverMutationError({ body: { detail: long } }, "fallback"),
              coverMutationError({ body: "<html>proxy failure</html>" }, "Safe fallback."),
              coverMutationError({ body: { detail: "<!doctype html><html>CSRF</html>" } }, "Safe fallback."),
            ];
            process.stdout.write(JSON.stringify(messages));
            """
        )
        assert messages[0] == "cover: Bad image."
        assert messages[1] == "Denied."
        assert len(messages[2]) == 240
        assert messages[3] == "Safe fallback."
        assert messages[4] == "Safe fallback."

    def test_successful_cover_urls_are_cache_busted(self):
        result = _run_node(
            """
            import { cacheBustedCoverUrl } from "./web/static/web/js/library/cover_editor.js";
            Date.now = () => 1234;
            process.stdout.write(JSON.stringify({
              plain: cacheBustedCoverUrl("/media/covers/book.png"),
              query: cacheBustedCoverUrl("/media/covers/book.png?x=1"),
              empty: cacheBustedCoverUrl(""),
            }));
            """
        )

        assert result == {
            "plain": "/media/covers/book.png?cover_v=1234",
            "query": "/media/covers/book.png?x=1&cover_v=1234",
            "empty": "",
        }
