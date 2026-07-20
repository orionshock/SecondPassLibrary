from __future__ import annotations

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class BookCoverProductUiContractTests:
    def test_detail_is_read_only_and_edit_uses_narrow_cover_endpoint(self):
        detail = (ROOT / "web/static/web/js/library/detail.js").read_text(encoding="utf-8")
        editor = (ROOT / "web/static/web/js/library/cover_editor.js").read_text(encoding="utf-8")
        detail_template = (ROOT / "web/templates/web/library/book_detail.html").read_text(
            encoding="utf-8"
        )
        edit_template = (ROOT / "web/templates/web/library/book_edit.html").read_text(
            encoding="utf-8"
        )
        edit_main = (ROOT / "web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")

        assert "cover_editor" not in detail
        assert 'id="book-cover-edit"' not in detail_template
        assert 'id="book-cover-modal"' not in detail_template
        assert "can_manage_library" not in edit_template
        assert 'id="book-edit-cover-editor"' in edit_template
        assert 'id="book-edit-cover-modal"' in edit_template
        assert 'id="book-edit-cover-change"' in edit_template
        assert 'aria-label="Change book cover"' in edit_template
        assert 'from "../library/cover_editor.js"' in edit_main
        assert "const canManage = canManageLibrary(me)" in edit_main
        assert "visible(root, true)" in editor
        assert "new FormData()" in editor
        assert 'data.append("cover", file)' in editor
        assert 'method: "POST"' in editor
        assert 'method: "DELETE"' in editor
        assert "/api/v1/library/books/${encodeURIComponent(String(bookId))}/cover/" in editor
        assert '"Content-Type"' not in editor

    def test_current_replace_reset_clear_and_bounded_states_are_present(self):
        editor = (ROOT / "web/static/web/js/library/cover_editor.js").read_text(encoding="utf-8")
        template = (ROOT / "web/templates/web/library/book_edit.html").read_text(
            encoding="utf-8"
        )

        assert 'id="book-edit-cover-current"' in template
        assert 'id="book-edit-cover-selection"' in template
        assert 'id="book-edit-cover-preview"' in template
        assert "URL.createObjectURL(file)" in editor
        assert "URL.revokeObjectURL(previewUrl)" in editor
        assert 'resetButton.addEventListener("click", closeModal)' in editor
        assert 'window.confirm("Clear this cover?")' in editor
        assert 'modal.showModal()' in editor
        assert 'modal.addEventListener("cancel"' in editor
        assert 'modal.addEventListener("close", () => openButton.focus())' in editor
        assert 'setStatus(statusEl, "Cover updated.", false)' in editor
        assert 'setStatus(statusEl, "Cover cleared.", false)' in editor
        assert 'console.error("Failed to replace book cover"' in editor
        assert 'console.error("Failed to clear book cover"' in editor

        messages = run_node_json(
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

    def test_cover_mutation_remains_separate_from_metadata_save(self):
        editor = (ROOT / "web/static/web/js/library/cover_editor.js").read_text(encoding="utf-8")
        edit_main = (ROOT / "web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        template = (ROOT / "web/templates/web/library/book_edit.html").read_text(
            encoding="utf-8"
        )

        assert 'id="book-edit-form"' in template
        assert 'id="book-edit-cover-form"' in template
        assert 'form="book-edit-form"' in template
        assert "buildBookPatchPayload" in edit_main
        assert 'method: "PATCH"' in edit_main
        assert 'form.addEventListener("submit"' in editor
        assert "buildBookPatchPayload" not in editor

    def test_cover_workflow_is_in_the_hero_not_identifiers(self):
        template = (ROOT / "web/templates/web/library/book_edit.html").read_text(
            encoding="utf-8"
        )

        hero = template.split('id="book-edit-header"', 1)[1].split(
            'id="book-edit-status"', 1
        )[0]
        identifiers = template.split('id="tab-idents"', 1)[1].split(
            'id="book-edit-cover-modal"', 1
        )[0]
        assert 'class="book-edit-hero' in hero
        assert 'id="book-edit-cover-current"' in hero
        assert 'id="book-edit-cover-change"' in hero
        assert 'id="book-edit-cover-' not in identifiers
        assert 'id="book-edit-identifiers"' in identifiers
        assert 'id="book-edit-file-info"' in identifiers
        assert 'id="book-edit-cover-submit"' in template
        assert 'id="book-edit-cover-clear"' in template
        assert 'id="book-edit-cover-reset"' in template

    def test_successful_cover_urls_are_cache_busted(self):
        result = run_node_json(
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
