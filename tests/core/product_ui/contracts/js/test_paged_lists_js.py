from pathlib import Path

import pytest

from tests.core.product_ui.helpers import ProductUiTestCase


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


class ProductUiPagedListJsContractsTests(ProductUiTestCase):
    def test_shelves_and_groups_use_shared_paged_list_helper(self):
        helper_js = Path("web/static/web/js/ui/paged_list.js").read_text(encoding="utf-8")
        shelves_list_js = Path("web/static/web/js/shelves/list.js").read_text(encoding="utf-8")
        shelves_shared_js = Path("web/static/web/js/shelves/shared.js").read_text(encoding="utf-8")
        groups_list_js = Path("web/static/web/js/groups/list.js").read_text(encoding="utf-8")
        groups_view_js = Path("web/static/web/js/groups/view.js").read_text(encoding="utf-8")
        groups_shared_js = Path("web/static/web/js/groups/shared.js").read_text(encoding="utf-8")
        main_js = Path("web/static/web/js/main.js").read_text(encoding="utf-8")

        self.assertIn("export async function createPagedListController", helper_js)
        self.assertIn("fetchJSON", helper_js)
        self.assertIn("setStatus", helper_js)
        self.assertIn("nextBtn.addEventListener", helper_js)
        self.assertIn("prevBtn.addEventListener", helper_js)
        self.assertIn("reloadFirstPage", helper_js)

        self.assertIn('from "../ui/paged_list.js"', shelves_list_js)
        self.assertIn("createPagedListController", shelves_list_js)
        self.assertNotIn("pagedController", shelves_shared_js)
        self.assertIn('from "../ui/paged_list.js"', groups_list_js)
        self.assertIn(
            'initialUrl: "/api/v1/library/groups/?include_preview_books=true"',
            groups_list_js,
        )
        self.assertIn('from "../ui/paged_list.js"', groups_view_js)
        self.assertNotIn("pagedListController", groups_shared_js)

        self.assertIn('shelves: { importer: () => import("./shelves/main.js")', main_js)
        self.assertIn('groups: { importer: () => import("./groups/main.js")', main_js)
