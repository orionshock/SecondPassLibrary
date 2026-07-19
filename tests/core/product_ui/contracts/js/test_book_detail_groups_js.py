from __future__ import annotations

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


def test_book_detail_group_renderer_lists_visible_groups_and_public_badge():
    result = run_node_json(
        r"""
        class TestElement {
          constructor(tag) {
            this.tagName = tag;
            this.children = [];
            this.attributes = {};
            this.className = "";
            this._text = "";
            this.classList = { add: (...names) => {
              const current = new Set(this.className.split(/\s+/).filter(Boolean));
              names.forEach((name) => current.add(String(name)));
              this.className = Array.from(current).join(" ");
            }};
          }
          get firstChild() { return this.children[0] || null; }
          appendChild(child) { this.children.push(child); return child; }
          removeChild(child) { this.children.splice(this.children.indexOf(child), 1); }
          setAttribute(name, value) { this.attributes[name] = String(value); }
          set textContent(value) { this._text = String(value); this.children = []; }
          get textContent() { return this._text + this.children.map((child) => child.textContent).join(""); }
        }
        globalThis.document = {
          createElement: (tag) => new TestElement(tag),
          createTextNode: (text) => { const node = new TestElement("#text"); node.textContent = text; return node; },
        };

        const { renderBookGroups } = await import("./web/static/web/js/library/detail.js");
        const populated = new TestElement("div");
        renderBookGroups(populated, [{
          id: "public-id",
          name: "Common Room",
          description: "Shared",
          is_public_group: true,
          membership_id: "must-not-render",
          user: "must-not-render",
        }]);
        const empty = new TestElement("div");
        renderBookGroups(empty, []);
        process.stdout.write(JSON.stringify({
          populatedText: populated.textContent,
          badgeClass: populated.children[0].children[0].children[0].children[0].className,
          href: populated.children[0].children[0].children[0].attributes.href,
          emptyText: empty.textContent,
        }));
        """
    )

    assert "Common Room" in result["populatedText"]
    assert "No visible groups" not in result["populatedText"]
    assert "group-badge--public" in result["badgeClass"]
    assert result["href"] == "/groups/public-id/"
    assert "must-not-render" not in result["populatedText"]
    assert result["emptyText"] == "No visible groups."


def test_book_edit_group_assignment_posts_book_id_contract():
    source = open(
        "web/static/web/js/book_edit/group_actions.js", encoding="utf-8"
    ).read()

    assert "JSON.stringify({ book_id: String(bookId) })" in source
    assert "JSON.stringify({ book: String(bookId) })" not in source
