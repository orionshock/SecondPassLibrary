from __future__ import annotations

import pytest

from tests.core.product_ui.js import run_node_json


pytestmark = [pytest.mark.product_ui, pytest.mark.static_contract]


DOM_FIXTURE = r"""
function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);
}

class TestElement {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.attributes = {};
    this._className = "";
    this._textContent = "";
    this.classList = {
      add: (...names) => {
        const current = new Set(this._className.split(/\s+/).filter(Boolean));
        for (const name of names) current.add(String(name));
        this._className = Array.from(current).join(" ");
      },
    };
  }
  set className(value) { this._className = String(value || ""); }
  get className() { return this._className; }
  set textContent(value) { this._textContent = String(value); this.children = []; }
  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }
  setAttribute(name, value) { this.attributes[String(name)] = String(value); }
  appendChild(child) { this.children.push(child); return child; }
  querySelector(className) {
    const wanted = className.startsWith(".") ? className.slice(1) : className;
    const visit = (node) => {
      if ((node.className || "").split(/\s+/).includes(wanted)) return node;
      for (const child of node.children || []) {
        const found = visit(child);
        if (found) return found;
      }
      return null;
    };
    return visit(this);
  }
  get outerHTML() {
    const attrs = [];
    if (this.className) attrs.push(`class="${escapeHtml(this.className)}"`);
    for (const [name, value] of Object.entries(this.attributes)) {
      attrs.push(`${escapeHtml(name)}="${escapeHtml(value)}"`);
    }
    const attrText = attrs.length ? ` ${attrs.join(" ")}` : "";
    const content = escapeHtml(this._textContent) + this.children.map((child) => child.outerHTML).join("");
    return `<${this.tagName}${attrText}>${content}</${this.tagName}>`;
  }
}

globalThis.document = {
  createElement(tag) {
    return new TestElement(String(tag));
  },
};
"""


class GroupBadgeJavaScriptTests:
    def test_group_badge_display_contract(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{
              groupBadgeText,
              groupDisplayName,
              renderGroupBadge,
            }} from "./web/static/web/js/ui/groups.js";

            const ordinary = {{
              id: "group-secret",
              internal_id: 123,
              name: "Fantasy Club",
              is_public_group: false,
            }};
            const publicGroup = {{
              id: "public-secret",
              name: "Common Room",
              is_public_group: true,
            }};
            const blank = {{ id: "blank-secret", name: "   " }};
            const ordinaryNode = renderGroupBadge(ordinary);
            const publicNode = renderGroupBadge(publicGroup, {{
              compact: true,
              className: "extra",
              element: "div",
            }});
            const blankNode = renderGroupBadge(blank);
            const nullNode = renderGroupBadge(null);

            process.stdout.write(JSON.stringify({{
              display: {{
                ordinary: groupDisplayName(ordinary),
                public: groupDisplayName(publicGroup),
                blank: groupDisplayName(blank),
                nullGroup: groupDisplayName(null),
                text: groupBadgeText(ordinary),
              }},
              ordinary: {{
                className: ordinaryNode.className,
                icon: ordinaryNode.querySelector(".group-badge__icon").textContent,
                text: ordinaryNode.textContent,
                html: ordinaryNode.outerHTML,
              }},
              publicGroup: {{
                className: publicNode.className,
                icon: publicNode.querySelector(".group-badge__icon").textContent,
                text: publicNode.textContent,
                html: publicNode.outerHTML,
              }},
              blankText: blankNode.textContent,
              nullText: nullNode.textContent,
            }}));
            """
        )

        assert result["display"] == {
            "ordinary": "Fantasy Club",
            "public": "Common Room",
            "blank": "Unknown group",
            "nullGroup": "Unknown group",
            "text": "Fantasy Club",
        }
        assert result["ordinary"]["className"] == "group-badge"
        assert result["ordinary"]["icon"] == "groups"
        assert result["ordinary"]["text"] == "groupsFantasy Club"
        assert result["publicGroup"]["className"] == (
            "group-badge group-badge--public group-badge--compact extra"
        )
        assert result["publicGroup"]["icon"] == "public"
        assert result["publicGroup"]["text"] == "publicCommon Room"
        assert result["blankText"] == "groupsUnknown group"
        assert result["nullText"] == "groupsUnknown group"

    def test_group_badge_does_not_render_internal_identifiers(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderGroupBadge }} from "./web/static/web/js/ui/groups.js";

            const group = {{
              id: "uuid-secret",
              pk: 123,
              internal_id: "internal-secret",
              membership_id: "membership-secret",
              name: "Visible Name",
              normalized_name: "visible-name",
              sort_name: "name-visible",
            }};
            const node = renderGroupBadge(group);
            process.stdout.write(JSON.stringify({{
              html: node.outerHTML,
              text: node.textContent,
            }}));
            """
        )

        for value in (result["html"], result["text"]):
            assert "Visible Name" in value
            assert "uuid-secret" not in value
            assert "123" not in value
            assert "internal-secret" not in value
            assert "membership-secret" not in value
            assert "visible-name" not in value
            assert "name-visible" not in value

    def test_group_badge_treats_malicious_group_names_as_text(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderGroupBadge }} from "./web/static/web/js/ui/groups.js";

            const group = {{
              name: "<strong>Public</strong><img src=x onerror=alert(1)>",
              is_public_group: true,
            }};
            const node = renderGroupBadge(group);
            process.stdout.write(JSON.stringify({{
              html: node.outerHTML,
              text: node.textContent,
            }}));
            """
        )

        assert "<strong>" in result["text"]
        assert "<img" in result["text"]
        assert "<strong>" not in result["html"]
        assert "<img" not in result["html"]
        assert "&lt;strong&gt;Public&lt;/strong&gt;" in result["html"]
        assert "&lt;img src=x onerror=alert(1)&gt;" in result["html"]
