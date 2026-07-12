from pathlib import Path

import pytest

from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiStatusAndImportsJsContractsTests(ProductUiTestCase):
    def test_product_ui_status_helpers_use_shared_helper(self):
        api_js = Path("web/static/web/js/api.js").read_text(encoding="utf-8")
        helper_js = Path("web/static/web/js/ui/status.js").read_text(encoding="utf-8")
        profile_js = Path("web/static/web/js/profile/main.js").read_text(encoding="utf-8")
        group_shared_js = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
        group_view_js = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
        shelves_shared_js = Path("web/static/web/js/shelves/shared.js").read_text(encoding="utf-8")
        shelves_view_js = Path("web/static/web/js/shelves/view.js").read_text(encoding="utf-8")
        book_edit_shared_js = Path("web/static/web/js/book_edit/shared.js").read_text(encoding="utf-8")
        book_edit_main_js = Path("web/static/web/js/book_edit/main.js").read_text(encoding="utf-8")
        book_edit_status_modules = [
            Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/book_edit/main.js",
                "web/static/web/js/book_edit/author_series_actions.js",
                "web/static/web/js/book_edit/group_actions.js",
                "web/static/web/js/book_edit/identifiers_actions.js",
                "web/static/web/js/book_edit/shelf_actions.js",
                "web/static/web/js/book_edit/shelves.js",
            )
        ]
        migrated_status_modules = [
            Path(path).read_text(encoding="utf-8")
            for path in (
                "web/static/web/js/profile/password.js",
                "web/static/web/js/library/list.js",
                "web/static/web/js/library/detail.js",
                "web/static/web/js/groups/new.js",
                "web/static/web/js/groups/edit.js",
                "web/static/web/js/imports/main.js",
                "web/static/web/js/server/settings.js",
                "web/static/web/js/users/list.js",
                "web/static/web/js/users/edit.js",
                "web/static/web/js/users/new.js",
                "web/static/web/js/users/memberships.js",
                "web/static/web/js/users/password_reset.js",
            )
        ]
        imports_js = Path("web/static/web/js/imports/main.js").read_text(encoding="utf-8")
        users_shared_js = Path("web/static/web/js/users/shared.js").read_text(encoding="utf-8")

        self.assertIn("export function jsonRequestHeaders", api_js)
        self.assertIn('const headers = { Accept: "application/json" }', api_js)
        self.assertIn('headers["Content-Type"] = "application/json"', api_js)
        self.assertIn('headers["X-CSRFToken"] = token', api_js)
        self.assertIn("jsonRequestHeaders", profile_js)
        self.assertIn("jsonRequestHeaders({ csrf: true })", profile_js)
        self.assertIn("jsonRequestHeaders({ csrf: true, contentType: false })", profile_js)
        self.assertNotIn("const csrf = getCsrfToken();", profile_js)
        self.assertIn("export function setStatus", helper_js)
        self.assertIn("export function clearStatus", helper_js)
        self.assertIn("document.querySelector", helper_js)
        self.assertIn("textContent", helper_js)
        self.assertIn("classList.toggle", helper_js)
        self.assertIn("errorClass", helper_js)
        self.assertIn('typeof options === "boolean"', helper_js)

        self.assertIn('from "../ui/status.js"', group_view_js)
        self.assertNotIn("export function setStatus", group_shared_js)
        self.assertNotIn("setSharedStatus", group_shared_js)
        self.assertIn('from "../ui/status.js"', shelves_view_js)
        self.assertNotIn("export function setStatus", shelves_shared_js)
        self.assertNotIn("setSharedStatus", shelves_shared_js)
        self.assertIn('from "../ui/status.js"', book_edit_main_js)
        self.assertNotIn("export function setInlineStatus", book_edit_shared_js)
        self.assertNotIn("setSharedStatus", book_edit_shared_js)
        self.assertNotIn("setInlineStatus", "\n".join(book_edit_status_modules))
        for module_js in migrated_status_modules:
            self.assertIn('from "../ui/status.js"', module_js)
        self.assertNotIn("function setStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setSaveStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setResetStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setMembershipsStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("function setAddStatus(", "\n".join(migrated_status_modules))
        self.assertNotIn("setElStatus", users_shared_js)
        self.assertIn('<section class="book import-result"', imports_js)
        self.assertIn('aria-label="Latest import result"', imports_js)
        self.assertIn("function itemRefs", imports_js)
        self.assertIn("function renderImportItem", imports_js)
        self.assertIn('class="import-result__item"', imports_js)
        self.assertIn('class="import-result__item-source"', imports_js)
        self.assertIn('class="muted import-result__item-message"', imports_js)
        self.assertIn("function resultCounts", imports_js)
        self.assertIn("item.source_label", imports_js)
        self.assertIn("item.safe_message", imports_js)
        self.assertIn("item.book_id", imports_js)
        self.assertIn("result.source_label", imports_js)
        self.assertIn("result.source_type", imports_js)
        self.assertIn("result.counts || {}", imports_js)
        self.assertIn('["imported", counts.imported]', imports_js)
        self.assertIn('["duplicate", counts.duplicate]', imports_js)
        self.assertIn('["conflict", counts.conflict]', imports_js)
        self.assertIn('["failed", counts.failed]', imports_js)
        self.assertIn('["skipped", counts.skipped]', imports_js)
        self.assertIn("Import complete.", imports_js)
        self.assertIn('href="/library/books/${encodeURIComponent(String(refs.bookId))}/"', imports_js)
        self.assertIn("renderImportResult(result)", imports_js)
        self.assertIn("setBusy(true)", imports_js)
        self.assertIn("large ZIP files may take a while", imports_js)
        self.assertIn("submitBtn.disabled = isBusy", imports_js)
        self.assertNotIn("operator_detail", imports_js)
        self.assertNotIn("Unknown source", imports_js)
        self.assertNotIn("Unknown item", imports_js)
        self.assertNotIn("source_filename", imports_js)
        self.assertNotIn("source_name", imports_js)
        self.assertNotIn("imported_count", imports_js)
        self.assertNotIn("duplicate_count", imports_js)
        self.assertNotIn("failed_count", imports_js)
        self.assertNotIn("run_id", imports_js)
        self.assertNotIn("fetchJSON(url)", imports_js)
        self.assertNotIn("Created import job", imports_js)
