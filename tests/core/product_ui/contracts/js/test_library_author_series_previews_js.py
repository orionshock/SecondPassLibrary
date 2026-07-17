from __future__ import annotations

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class LibraryAuthorSeriesPreviewJavaScriptTests:
    def test_author_and_series_rows_render_preview_strips_from_payloads(self):
        result = run_node_json(
            """
            globalThis.window = { location: { origin: "http://testserver" } };
            const {
              renderAuthors,
              renderSeries,
            } = await import("./web/static/web/js/library/list.js");

            const authorHtml = renderAuthors({
              results: [{
                id: "author-1",
                name: "Ada Author",
                book_count: 2,
                preview_books: [
                  { id: "book-1", title: "Visible One", cover_url: "/media/covers/one.webp" },
                  { id: "book-2", title: "Visible Two", cover_url: null },
                ],
              }],
            });
            const seriesHtml = renderSeries({
              results: [{
                id: "series-1",
                name: "First Series",
                book_count: 1,
                preview_books: [
                  { id: "book-3", title: "Series Book", cover_url: "/media/covers/series.webp" },
                ],
              }],
            });
            const emptyAuthorHtml = renderAuthors({
              results: [{ id: "author-empty", name: "No Covers", book_count: 0, preview_books: [] }],
            });
            const emptySeriesHtml = renderSeries({
              results: [{ id: "series-empty", name: "No Covers", book_count: 0, preview_books: [] }],
            });

            process.stdout.write(JSON.stringify({
              authorHtml,
              seriesHtml,
              emptyAuthorHtml,
              emptySeriesHtml,
            }));
            """
        )

        author_html = result["authorHtml"]
        series_html = result["seriesHtml"]
        assert "Ada Author" in author_html
        assert "2 Books" in author_html
        assert 'class="cover-preview-strip"' in author_html
        assert 'data-action="browse-author"' in author_html
        assert 'href="/library/books/book-1/?view=author&amp;author=author-1"' in author_html
        assert "Visible One" in author_html

        assert "First Series" in series_html
        assert "1 Book" in series_html
        assert 'class="cover-preview-strip"' in series_html
        assert 'data-action="browse-series"' in series_html
        assert 'href="/library/books/book-3/?view=series&amp;series=series-1"' in series_html
        assert "Series Book" in series_html

        assert 'class="cover-preview-strip"' not in result["emptyAuthorHtml"]
        assert 'class="cover-preview-strip"' not in result["emptySeriesHtml"]

    def test_author_and_series_preview_rows_do_not_render_hidden_file_metadata(self):
        result = run_node_json(
            """
            globalThis.window = { location: { origin: "http://testserver" } };
            const {
              renderAuthors,
              renderSeries,
            } = await import("./web/static/web/js/library/list.js");

            const maliciousBook = {
              id: "book-public-id",
              title: "<img src=x onerror=alert(1)>",
              cover_url: "/media/covers/safe.webp",
              download_url: "/api/v1/library/books/book-public-id/download/",
              storage_path: "userdata/media/books/private.epub",
              source_filename: "private-source.epub",
              checksum: "checksum-secret",
              identifiers: [{ scheme: "isbn", value: "secret" }],
              groups: [{ id: "group-secret", name: "Hidden" }],
              internal_id: 42,
            };
            const authorHtml = renderAuthors({
              results: [{
                id: "author-1",
                name: "Ada",
                book_count: 1,
                preview_books: [maliciousBook],
              }],
            });
            const seriesHtml = renderSeries({
              results: [{
                id: "series-1",
                name: "Series",
                book_count: 1,
                preview_books: [maliciousBook],
              }],
            });

            process.stdout.write(JSON.stringify({ authorHtml, seriesHtml }));
            """
        )

        combined = result["authorHtml"] + result["seriesHtml"]
        assert "<img" not in combined
        assert "&lt;img src=x onerror=alert(1)&gt;" in combined
        assert "download_url" not in combined
        assert "/download/" not in combined
        assert "userdata/media/books/private.epub" not in combined
        assert "private-source.epub" not in combined
        assert "checksum-secret" not in combined
        assert "identifiers" not in combined
        assert "group-secret" not in combined
        assert "internal_id" not in combined
        assert "42" not in combined

    def test_library_requests_author_and_series_previews_without_books_or_tags(self):
        source = (ROOT / "web/static/web/js/library/list.js").read_text(encoding="utf-8")
        tag_source = (ROOT / "web/static/web/js/library/catalog_tags.js").read_text(encoding="utf-8")

        assert 'urlWithParams("/api/v1/library/authors/"' in source
        assert 'urlWithParams("/api/v1/library/series/"' in source
        assert source.count('include_preview_books: "true"') == 2
        assert 'urlWithParams("/api/v1/library/books/"' in source
        books_block = source.split('urlWithParams("/api/v1/library/books/"', 1)[1].split(
            "function locationParamsForState", 1
        )[0]
        assert "include_preview_books" not in books_block
        assert "include_preview_books" not in tag_source

    def test_library_preview_strip_layout_is_right_aligned_and_responsive(self):
        css = (ROOT / "web/static/web/css/library.css").read_text(encoding="utf-8")

        assert ".library-browse-row .cover-preview-strip" in css
        assert "justify-self: end" in css
        assert "justify-content: flex-end" in css
        assert "@media (max-width: 720px)" in css
        assert "justify-self: start" in css
        assert "justify-content: flex-start" in css
