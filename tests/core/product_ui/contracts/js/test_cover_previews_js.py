from __future__ import annotations

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class CoverPreviewStripJavaScriptTests:
    def test_preview_strip_renders_detail_links_for_visible_cover_books(self):
        result = run_node_json(
            """
            import { renderCoverPreviewStrip } from "./web/static/web/js/ui/cover_previews.js";

            const html = renderCoverPreviewStrip([
              { id: "book one", title: "First Book", cover_url: "/media/covers/first.webp" },
              { id: "book/two", title: "Second Book", cover_url: "/media/covers/second.png" },
              { id: "ignored", title: "", cover_url: "/media/covers/ignored.png" },
              null,
            ]);

            process.stdout.write(JSON.stringify({ html }));
            """
        )

        html = result["html"]
        assert html.count('class="cover-preview-button"') == 2
        assert 'class="cover-preview-strip" aria-label="View books previews"' in html
        assert 'href="/library/books/book%20one/"' in html
        assert 'href="/library/books/book%2Ftwo/"' in html
        assert 'title="First Book"' in html
        assert 'aria-label="Open book details for First Book"' in html
        assert 'data-cover-url="/media/covers/first.webp"' in html
        assert 'data-cover-title="Second Book"' in html
        assert "ignored" not in html

    def test_preview_strip_supports_context_links_and_button_actions(self):
        result = run_node_json(
            """
            import { renderCoverPreviewStrip } from "./web/static/web/js/ui/cover_previews.js";

            const contextHtml = renderCoverPreviewStrip(
              [{ id: "book-1", title: "Context Book", cover_url: "/covers/context.webp" }],
              { href: "/library/?view=author&author=ada", actionLabel: "View author Ada" }
            );
            const buttonHtml = renderCoverPreviewStrip(
              [{ id: "book-2", title: "Button Book", cover_url: "" }],
              {
                action: "browse-author",
                actionLabel: "Browse author",
                contextId: "author-1",
                contextName: "Ada",
                bookHref: () => "",
              }
            );
            const emptyHtml = renderCoverPreviewStrip([]);
            const missingTitleHtml = renderCoverPreviewStrip([{ id: "book-3" }]);

            process.stdout.write(JSON.stringify({
              contextHtml,
              buttonHtml,
              emptyHtml,
              missingTitleHtml,
            }));
            """
        )

        context_html = result["contextHtml"]
        button_html = result["buttonHtml"]
        assert 'href="/library/?view=author&amp;author=ada"' in context_html
        assert 'aria-label="View author Ada; preview includes Context Book"' in context_html
        assert "/library/books/book-1/" not in context_html
        assert "<button" in button_html
        assert 'type="button"' in button_html
        assert 'data-action="browse-author"' in button_html
        assert 'data-id="author-1"' in button_html
        assert 'data-name="Ada"' in button_html
        assert 'aria-label="Browse author; preview includes Button Book"' in button_html
        assert result["emptyHtml"] == ""
        assert result["missingTitleHtml"] == ""

    def test_preview_strip_escapes_malicious_titles_labels_and_attributes(self):
        result = run_node_json(
            """
            import { renderCoverPreviewStrip } from "./web/static/web/js/ui/cover_previews.js";

            const html = renderCoverPreviewStrip(
              [{
                id: "safe-book",
                title: "<img src=x onerror=alert(1)>",
                cover_url: "/media/covers/a.webp\\" onmouseover=\\"alert(2)",
              }],
              {
                action: "browse\\" onclick=\\"alert(3)",
                actionLabel: "Open <script>alert(4)</script>",
                contextId: "ctx\\" onclick=\\"alert(5)",
                contextName: "Name <b>bad</b>",
                bookHref: () => "",
              }
            );

            process.stdout.write(JSON.stringify({ html }));
            """
        )

        html = result["html"]
        assert "<img" not in html
        assert "<script>" not in html
        assert "<b>" not in html
        assert 'onmouseover="alert(2)' not in html
        assert 'onclick="alert(3)' not in html
        assert 'onclick="alert(5)' not in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html
        assert "Open &lt;script&gt;alert(4)&lt;/script&gt; previews" in html
        assert "/media/covers/a.webp&quot; onmouseover=&quot;alert(2)" in html
        assert 'data-action="browse&quot; onclick=&quot;alert(3)"' in html
        assert 'data-id="ctx&quot; onclick=&quot;alert(5)"' in html
        assert 'data-name="Name &lt;b&gt;bad&lt;/b&gt;"' in html

    def test_preview_strip_does_not_display_storage_paths_or_internal_fields(self):
        result = run_node_json(
            """
            import { renderCoverPreviewStrip } from "./web/static/web/js/ui/cover_previews.js";

            const html = renderCoverPreviewStrip([{
              id: "book-public-id",
              title: "Visible Title",
              cover_url: "/media/covers/public.webp",
              storage_path: "userdata/media/books/private.epub",
              source_filename: "private-source.epub",
              checksum: "checksum-secret",
              internal_id: 123,
            }]);

            process.stdout.write(JSON.stringify({ html }));
            """
        )

        html = result["html"]
        assert "Visible Title" in html
        assert "/library/books/book-public-id/" in html
        assert "userdata/media/books/private.epub" not in html
        assert "private-source.epub" not in html
        assert "checksum-secret" not in html
        assert "internal_id" not in html
        assert "123" not in html
