import pytest

from tests.core.product_ui.js import REPOSITORY_ROOT

pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class CatalogTagProductUiContractTests:
    def test_library_list_renders_current_nested_tag_names(self):
        source = (REPOSITORY_ROOT / "web/static/web/js/library/list.js").read_text(
            encoding="utf-8"
        )

        assert "function renderTags(tags)" in source
        assert "tag && tag.name" in source
        assert "renderTags(b.tags)" in source
        assert "b.subjects" not in source

    def test_book_edit_uses_shared_uncapped_pagination_for_tags(self):
        source = (REPOSITORY_ROOT / "web/static/web/js/book_edit/main.js").read_text(
            encoding="utf-8"
        )
        shared = (REPOSITORY_ROOT / "web/static/web/js/book_edit/shared.js").read_text(
            encoding="utf-8"
        )

        assert "fetchAllPaginatedResults" in source
        assert 'fetchAllPaginatedResults("/api/v1/library/tags/")' in source
        assert "fetchAllPages" not in source
        assert "fetchAllPages" not in shared
        assert "< 50" not in source
        assert "< 50" not in shared

    def test_tag_load_failure_is_bounded_and_diagnostics_stay_console_only(self):
        source = (REPOSITORY_ROOT / "web/static/web/js/book_edit/main.js").read_text(
            encoding="utf-8"
        )
        template = (
            REPOSITORY_ROOT / "web/templates/web/library/book_edit.html"
        ).read_text(encoding="utf-8")

        assert 'id="book-edit-catalog-tags-status"' in template
        assert 'setStatus(catalogTagsStatusEl, "Failed to load Catalog Tags.", true)' in source
        assert 'console.error("Failed to load Catalog Tags", e)' in source
        assert len("Failed to load Catalog Tags.") < 80

    def test_book_patch_still_submits_tag_names(self):
        source = (
            REPOSITORY_ROOT / "web/static/web/js/book_edit/metadata.js"
        ).read_text(encoding="utf-8")

        assert "catalog_tags: catalogTags.map" in source
        assert "String(tag.name || \"\").trim()" in source
