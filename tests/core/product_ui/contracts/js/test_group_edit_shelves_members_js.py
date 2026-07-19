from pathlib import Path

import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT as ROOT
from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_group_edit_shelves_render_safe_previews_and_accessible_actions():
    module_uri = (ROOT / "web/static/web/js/groups/shared.js").as_uri()
    result = run_node_json(
        f"""
        const mod = await import("{module_uri}");
        const html = mod.renderGroupShelvesCompact({{
          results: [{{
            id: "shelf-1",
            name: "Empty Shelf",
            description: "Still visible",
            item_count: 0,
            can_edit: true,
            preview_books: [],
          }}, {{
            id: "shelf-2",
            name: "Preview Shelf",
            item_count: 1,
            can_edit: true,
            preview_books: [{{
              id: "book-internal-id",
              title: "Visible Preview",
              cover_url: "/safe-cover/",
              download_url: "SECRET_DOWNLOAD",
              checksum: "SECRET_CHECKSUM",
              storage_path: "SECRET_STORAGE",
              source_filename: "SECRET_SOURCE",
            }}],
          }}],
        }}, {{ canEdit: true }});
        console.log(JSON.stringify({{ html }}));
        """
    )

    html = result["html"]
    assert "Empty Shelf" in html
    assert "0 items" in html
    assert "cover-preview-strip" in html
    assert "Visible Preview" in html
    assert 'href="/shelves/shelf-1/"' in html
    assert 'href="/shelves/shelf-1/edit/"' in html
    assert 'aria-label="View shelf Empty Shelf"' in html
    assert 'aria-label="Edit shelf Empty Shelf"' in html
    assert 'target="_blank"' not in html
    for secret in (
        "book-internal-id",
        "SECRET_DOWNLOAD",
        "SECRET_CHECKSUM",
        "SECRET_STORAGE",
        "SECRET_SOURCE",
    ):
        assert secret not in html


def test_group_edit_shelves_request_previews_and_members_keep_safe_controls():
    shelves = Path("web/static/web/js/groups/shelves.js").read_text(encoding="utf-8")
    memberships = Path("web/static/web/js/groups/memberships.js").read_text(
        encoding="utf-8"
    )
    shared = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
    template = Path("web/templates/web/groups/edit.html").read_text(encoding="utf-8")

    assert "include_preview_books=true" in shelves
    assert "renderCoverPreviewStrip(s && s.preview_books" in shared
    assert "includeDisplayName: false" in shared
    assert 'data-action="member-remove"' in shared
    assert 'data-action="member-curator"' in shared
    assert "Public fallback group; curator unavailable." in shared
    assert "addMemberRole.disabled = true" in memberships
    assert "groupMutationErrorMessage" in memberships
    assert 'data-tab-panel="books"' in template
    assert 'data-tab-panel="add-books"' in template
    assert 'id="group-edit-book-search-form"' in template
    assert 'id="group-edit-books-results"' in template
