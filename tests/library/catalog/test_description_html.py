from django.test import SimpleTestCase

from library.catalog.description_html import sanitize_book_description


class BookDescriptionSanitizerTests(SimpleTestCase):
    def test_preserves_exact_supported_markup_without_attributes(self):
        source = (
            '<p class="lead">A <b>bold</b> and <strong>strong</strong> '
            '<i>italic</i> and <em>emphasized</em> line<br data-x="1">next</p>'
            '<ul><li>First</li></ul><ol><li>Second</li></ol>'
        )

        sanitized = sanitize_book_description(source)

        self.assertEqual(
            sanitized,
            "<p>A <b>bold</b> and <strong>strong</strong> "
            "<i>italic</i> and <em>emphasized</em> line<br>next</p>"
            "<ul><li>First</li></ul><ol><li>Second</li></ol>",
        )

    def test_removes_unsupported_markup_attributes_and_executable_content(self):
        source = (
            '<div><a href="https://example.test">linked</a>'
            '<img src=x onerror="alert(1)"><span style="color:red">text</span>'
            '<table><tr><td>cell</td></tr></table></div>'
            '<p id="x" class="y" onclick="alert(1)" style="color:red">safe</p>'
            '<script>alert("script")</script><style>body{display:none}</style>'
        )

        sanitized = sanitize_book_description(source)

        self.assertEqual(sanitized, "linkedtextcell<p>safe</p>")
        for forbidden in ("href", "src", "onerror", "onclick", "style", "class", "script"):
            self.assertNotIn(forbidden, sanitized)

    def test_preserves_plain_text_and_html_entity_semantics(self):
        self.assertEqual(
            sanitize_book_description("Plain text\nwith a raw newline"),
            "Plain text\nwith a raw newline",
        )
        self.assertEqual(
            sanitize_book_description("Space&#x20;&amp; value"),
            "Space &amp; value",
        )

    def test_keeps_nested_supported_markup_structurally_valid(self):
        self.assertEqual(
            sanitize_book_description("<ul><li><p>Nested <em>value</em></p></li></ul>"),
            "<ul><li><p>Nested <em>value</em></p></li></ul>",
        )
