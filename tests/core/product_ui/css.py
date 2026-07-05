"""Helpers for Product UI CSS contract tests."""
from pathlib import Path
import re


CSS_ENTRYPOINT = Path("web/static/web/app.css")
CSS_IMPORT_RE = re.compile(r'@import\s+url\("(?P<path>[^"]+)"\);')


def product_ui_css_text() -> str:
    """Return the Product UI CSS entrypoint plus imported partials."""
    manifest = CSS_ENTRYPOINT.read_text(encoding="utf-8")
    chunks = [manifest]
    static_root = CSS_ENTRYPOINT.parent.resolve()

    for match in CSS_IMPORT_RE.finditer(manifest):
        imported_path = (CSS_ENTRYPOINT.parent / match.group("path")).resolve()
        if not imported_path.is_relative_to(static_root):
            raise AssertionError(f"CSS import escapes static root: {imported_path}")
        chunks.append(imported_path.read_text(encoding="utf-8"))

    return "\n".join(chunks)
