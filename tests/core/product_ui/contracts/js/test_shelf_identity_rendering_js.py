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

function dataAttributeName(name) {
  return `data-${String(name).replace(/[A-Z]/g, (ch) => `-${ch.toLowerCase()}`)}`;
}

class TestElement {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.attributes = {};
    this._className = "";
    this._textContent = "";
    this.dataset = new Proxy({}, {
      set: (target, key, value) => {
        target[key] = String(value);
        this.attributes[dataAttributeName(key)] = String(value);
        return true;
      },
    });
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
  querySelectorAll(className) {
    const wanted = className.startsWith(".") ? className.slice(1) : className;
    const matches = [];
    const visit = (node) => {
      if ((node.className || "").split(/\s+/).includes(wanted)) matches.push(node);
      for (const child of node.children || []) visit(child);
    };
    visit(this);
    return matches;
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
  body: { dataset: { advancedLibraryGroups: "true" } },
  createElement(tag) {
    return new TestElement(String(tag));
  },
};
"""


class ShelfIdentityRenderingJavaScriptTests:
    def test_user_owned_shelf_metadata_uses_compact_owner_identity(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{
              renderShelfMetadata,
              shelfCreatedByDisplay,
              shelfMetadataLine,
            }} from "./web/static/web/js/shelves/shared.js";

            const shelf = {{
              id: "shelf-secret",
              name: "Listed Shelf",
              owner_type: "user",
              visibility: "listed",
              item_count: 2,
              owner_user: {{
                profile_id: "profile-secret",
                id: "raw-user-secret",
                pk: 9,
                membership_id: "membership-secret",
                username: "reader",
                email: "reader@example.test",
              }},
              created_by: {{
                profile_id: "creator-profile-secret",
                id: "creator-raw-secret",
                username: "creator",
                email: "creator@example.test",
              }},
            }};
            const metadataNode = renderShelfMetadata(shelf);
            process.stdout.write(JSON.stringify({{
              htmlLine: shelfMetadataLine(shelf),
              renderedHtml: metadataNode.outerHTML,
              renderedText: metadataNode.textContent,
              pieces: metadataNode.querySelectorAll(".shelf-metadata-piece").length,
              createdBy: shelfCreatedByDisplay(shelf),
            }}));
            """
        )

        for value in (
            result["htmlLine"],
            result["renderedHtml"],
            result["renderedText"],
            result["createdBy"],
        ):
            assert "reader" in value or "creator" in value
            assert "reader@example.test" not in value
            assert "creator@example.test" not in value
            assert "profile-secret" not in value
            assert "raw-user-secret" not in value
            assert "membership-secret" not in value
            assert "creator-profile-secret" not in value
            assert "creator-raw-secret" not in value

        assert "Shared by" in result["renderedText"]
        assert "Listed" in result["renderedText"]
        assert "2 items" in result["renderedText"]
        assert result["createdBy"] == "Created by <@creator>"
        assert result["pieces"] == 3

    def test_private_user_shelf_hides_owner_segment_but_keeps_metadata(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderShelfMetadata, shelfMetadataLine }} from "./web/static/web/js/shelves/shared.js";

            const shelf = {{
              owner_type: "user",
              visibility: "private",
              item_count: 1,
              owner_user: {{ username: "reader", email: "reader@example.test" }},
            }};
            const metadataNode = renderShelfMetadata(shelf);
            process.stdout.write(JSON.stringify({{
              htmlLine: shelfMetadataLine(shelf),
              renderedHtml: metadataNode.outerHTML,
              renderedText: metadataNode.textContent,
            }}));
            """
        )

        assert "Shared by" not in result["renderedText"]
        assert "reader" not in result["renderedText"]
        assert "reader@example.test" not in result["renderedHtml"]
        assert result["renderedText"] == "Private1 item"
        assert "Private" in result["htmlLine"]
        assert "1 item" in result["htmlLine"]

    def test_group_owned_shelf_metadata_uses_group_name_without_internal_ids(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderShelfMetadata, shelfMetadataLine }} from "./web/static/web/js/shelves/shared.js";

            const shelf = {{
              owner_type: "group",
              visibility: "private",
              item_count: 4,
              owner_group: {{
                id: "group-uuid-secret",
                pk: 77,
                internal_id: "group-internal-secret",
                name: "Fantasy Club",
                is_public_group: false,
              }},
            }};
            const metadataNode = renderShelfMetadata(shelf);
            process.stdout.write(JSON.stringify({{
              htmlLine: shelfMetadataLine(shelf),
              renderedHtml: metadataNode.outerHTML,
              renderedText: metadataNode.textContent,
            }}));
            """
        )

        for value in (result["htmlLine"], result["renderedHtml"], result["renderedText"]):
            assert "Fantasy Club" in value
            assert "group-uuid-secret" not in value
            assert "group-internal-secret" not in value
            assert "77" not in value
            assert "Private" not in value

        assert "4 items" in result["renderedText"]

    def test_group_shelf_metadata_respects_public_and_advanced_mode_display(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderShelfMetadata }} from "./web/static/web/js/shelves/shared.js";

            const customShelf = {{
              owner_type: "group",
              item_count: 1,
              owner_group: {{ id: "custom-secret", name: "Hidden Club", is_public_group: false }},
            }};
            const publicShelf = {{
              owner_type: "group",
              item_count: 1,
              owner_group: {{ id: "public-secret", name: "Common Room", is_public_group: true }},
            }};
            document.body.dataset.advancedLibraryGroups = "false";
            const disabledCustom = renderShelfMetadata(customShelf);
            const disabledPublic = renderShelfMetadata(publicShelf);
            document.body.dataset.advancedLibraryGroups = "true";
            const enabledCustom = renderShelfMetadata(customShelf);

            process.stdout.write(JSON.stringify({{
              disabledCustomText: disabledCustom.textContent,
              disabledCustomHtml: disabledCustom.outerHTML,
              disabledPublicText: disabledPublic.textContent,
              disabledPublicHtml: disabledPublic.outerHTML,
              enabledCustomText: enabledCustom.textContent,
              enabledCustomHtml: enabledCustom.outerHTML,
            }}));
            """
        )

        assert result["disabledCustomText"] == "1 item"
        assert "Hidden Club" not in result["disabledCustomHtml"]
        assert "custom-secret" not in result["disabledCustomHtml"]
        assert "Common Room" in result["disabledPublicText"]
        assert "public-secret" not in result["disabledPublicHtml"]
        assert "Hidden Club" in result["enabledCustomText"]
        assert "custom-secret" not in result["enabledCustomHtml"]

    def test_shelf_metadata_treats_malicious_owner_and_group_names_as_text(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderShelfMetadata }} from "./web/static/web/js/shelves/shared.js";

            const listedUserShelf = {{
              owner_type: "user",
              visibility: "listed",
              item_count: 1,
              owner_user: {{ username: "reader<img src=x onerror=alert(1)>" }},
            }};
            const groupShelf = {{
              owner_type: "group",
              item_count: 1,
              owner_group: {{
                name: "<strong>Public</strong><img src=x onerror=alert(2)>",
                is_public_group: true,
              }},
            }};
            const userNode = renderShelfMetadata(listedUserShelf);
            const groupNode = renderShelfMetadata(groupShelf);

            process.stdout.write(JSON.stringify({{
              userText: userNode.textContent,
              userHtml: userNode.outerHTML,
              groupText: groupNode.textContent,
              groupHtml: groupNode.outerHTML,
            }}));
            """
        )

        assert "<img" in result["userText"]
        assert "<strong>" in result["groupText"]
        assert "<img" in result["groupText"]
        assert "<img" not in result["userHtml"]
        assert "<strong>" not in result["groupHtml"]
        assert "&lt;img src=x onerror=alert(1)&gt;" in result["userHtml"]
        assert "&lt;strong&gt;Public&lt;/strong&gt;" in result["groupHtml"]
