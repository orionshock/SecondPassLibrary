from __future__ import annotations

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


TOGGLE_DOM_FIXTURE = r"""
class ClassList {
  constructor() {
    this.values = new Set();
  }
  toggle(name, on) {
    if (on) this.values.add(name);
    else this.values.delete(name);
  }
  contains(name) {
    return this.values.has(name);
  }
}

class TestElement {}

globalThis.HTMLElement = TestElement;
globalThis.CSS = { escape: (value) => String(value).replace(/"/g, '\\"') };
"""


class LibraryProseJavaScriptTests:
    def test_author_biography_and_series_summary_context_rendering(self):
        result = run_node_json(
            """
            import { renderLibraryContext } from "./web/static/web/js/library/prose.js";

            const authorHtml = renderLibraryContext({
              filter: {
                kind: "author",
                id: "author 1",
                label: "Author",
                name: "Ada Lovelace",
                prose: "Mathematician and writer.",
                proseLabel: "Biography",
              },
              canEdit: true,
            });
            const seriesHtml = renderLibraryContext({
              filter: {
                kind: "series",
                id: "series/1",
                label: "Series",
                name: "Example Series",
                prose: "A compact summary.",
                proseLabel: "Summary",
              },
            });

            process.stdout.write(JSON.stringify({ authorHtml, seriesHtml }));
            """
        )

        author_html = result["authorHtml"]
        series_html = result["seriesHtml"]
        assert "Author: <strong>Ada Lovelace</strong>" in author_html
        assert "Mathematician and writer." in author_html
        assert 'data-action="edit-library-context"' in author_html
        assert 'id="library-author-prose-author-1"' in author_html
        assert "Biography" not in author_html
        assert "Series: <strong>Example Series</strong>" in series_html
        assert "A compact summary." in series_html
        assert 'data-action="edit-library-context"' not in series_html
        assert 'id="library-series-prose-series-1"' in series_html
        assert "Description" not in author_html
        assert "Description" not in series_html

    def test_empty_missing_prose_and_edit_controls_contract(self):
        result = run_node_json(
            """
            import {
              renderContextProseBlock,
              renderLibraryContext,
            } from "./web/static/web/js/library/prose.js";

            const emptyBlock = renderContextProseBlock({
              text: "   ",
              idPrefix: "author",
              itemId: "empty",
            });
            const missingContext = renderLibraryContext({
              filter: {
                kind: "author",
                id: "empty",
                label: "Author",
                name: "No Prose",
                prose: "",
                proseLabel: "Biography",
              },
              status: "Saved.",
              error: "Could not save.",
            });
            const editing = renderLibraryContext({
              filter: {
                kind: "series",
                id: "series-2",
                label: "Series",
                name: "Original Series",
                prose: "Original summary.",
                proseLabel: "Summary",
              },
              editing: true,
              editName: "Edited Series",
              editProse: "Edited summary.",
              status: "Saving...",
            });

            process.stdout.write(JSON.stringify({ emptyBlock, missingContext, editing }));
            """
        )

        assert result["emptyBlock"] == ""
        assert 'class="library-context__prose"' not in result["missingContext"]
        assert "Saved." in result["missingContext"]
        assert "Could not save." in result["missingContext"]
        assert 'name="library-context-name"' in result["editing"]
        assert 'value="Edited Series"' in result["editing"]
        assert 'name="library-context-prose"' in result["editing"]
        assert ">Summary</span>" in result["editing"]
        assert "Edited summary." in result["editing"]
        assert 'data-action="save-library-context"' in result["editing"]
        assert 'data-action="cancel-library-context-edit"' in result["editing"]
        assert 'data-action="clear-library-filter"' not in result["editing"]
        assert ">Clear</button>" not in result["editing"]

    def test_prose_markup_escapes_malicious_values(self):
        result = run_node_json(
            """
            import { renderLibraryContext } from "./web/static/web/js/library/prose.js";

            const html = renderLibraryContext({
              filter: {
                kind: "author\\" onclick=\\"alert(1)",
                id: "id<script>",
                label: "Author <img src=x onerror=alert(2)>",
                name: "<strong>Ada</strong>",
                prose: "<script>alert(3)</script>",
                proseLabel: "Bio <b>label</b>",
              },
              canEdit: true,
              status: "<em>Saved</em>",
              error: "<iframe src=x></iframe>",
            });

            process.stdout.write(JSON.stringify({ html }));
            """
        )

        html = result["html"]
        assert "<img" not in html
        assert "<script>" not in html
        assert "<em>" not in html
        assert "<iframe" not in html
        assert "<b>" not in html
        assert "&lt;img src=x onerror=alert(2)&gt;" in html
        assert "<strong>&lt;strong&gt;Ada&lt;/strong&gt;</strong>" in html
        assert "&lt;script&gt;alert(3)&lt;/script&gt;" in html
        assert "&lt;em&gt;Saved&lt;/em&gt;" in html
        assert "&lt;iframe src=x&gt;&lt;/iframe&gt;" in html

    def test_toggle_prose_block_updates_expansion_state(self):
        result = run_node_json(
            f"""
            {TOGGLE_DOM_FIXTURE}
            import {{ toggleProseBlock }} from "./web/static/web/js/library/prose.js";

            const target = new HTMLElement();
            target.classList = new ClassList();
            const button = new HTMLElement();
            button.attributes = {{ "data-target": "prose-1", "aria-expanded": "false" }};
            button.textContent = "Show More";
            button.getAttribute = (name) => button.attributes[name] || "";
            button.setAttribute = (name, value) => {{ button.attributes[name] = String(value); }};
            const root = {{
              querySelector(selector) {{
                return selector === "#prose-1" ? target : null;
              }},
            }};

            toggleProseBlock(button, root);
            const afterOpen = {{
              expanded: button.attributes["aria-expanded"],
              text: button.textContent,
              classOn: target.classList.contains("is-expanded"),
            }};
            toggleProseBlock(button, root);
            const afterClose = {{
              expanded: button.attributes["aria-expanded"],
              text: button.textContent,
              classOn: target.classList.contains("is-expanded"),
            }};

            process.stdout.write(JSON.stringify({{ afterOpen, afterClose }}));
            """
        )

        assert result == {
            "afterOpen": {
                "expanded": "true",
                "text": "Show Less",
                "classOn": True,
            },
            "afterClose": {
                "expanded": "false",
                "text": "Show More",
                "classOn": False,
            },
        }
