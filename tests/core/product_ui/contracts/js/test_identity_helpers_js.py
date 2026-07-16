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
  createElement(tag) {
    return new TestElement(String(tag));
  },
};
"""


class IdentityHelperJavaScriptTests:
    def test_display_name_and_identity_text_contract(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{
              userDisplayName,
              userHandle,
              userIdentityText,
            }} from "./web/static/web/js/ui/identity.js";

            const users = {{
              usernameOnly: {{ profile_id: "profile-1", username: "reader" }},
              fullName: {{ username: "ada", first_name: "Ada", last_name: "Lovelace" }},
              firstOnly: {{ username: "grace", first_name: "Grace", last_name: "" }},
              lastOnly: {{ username: "hopper", first_name: "", last_name: "Hopper" }},
              blankOptionals: {{ username: "blank", first_name: " ", last_name: null }},
              empty: {{}},
            }};

            process.stdout.write(JSON.stringify({{
              usernameOnly: {{
                display: userDisplayName(users.usernameOnly),
                handle: userHandle(users.usernameOnly),
                text: userIdentityText(users.usernameOnly),
              }},
              fullName: userIdentityText(users.fullName),
              firstOnly: userIdentityText(users.firstOnly),
              lastOnly: userIdentityText(users.lastOnly),
              blankOptionals: userIdentityText(users.blankOptionals),
              empty: userIdentityText(users.empty),
              nullUser: userIdentityText(null),
              noDisplayName: userIdentityText(users.fullName, {{ includeDisplayName: false }}),
            }}));
            """
        )

        assert result == {
            "usernameOnly": {
                "display": "",
                "handle": "<@reader>",
                "text": "<@reader>",
            },
            "fullName": "Ada Lovelace, <@ada>",
            "firstOnly": "Grace, <@grace>",
            "lastOnly": "Hopper, <@hopper>",
            "blankOptionals": "<@blank>",
            "empty": "Unknown user",
            "nullUser": "Unknown user",
            "noDisplayName": "<@ada>",
        }

    def test_privacy_boundary_omits_internal_ids_and_email_by_default(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{
              renderUserIdentity,
              userIdentityText,
            }} from "./web/static/web/js/ui/identity.js";

            const user = {{
              profile_id: "profile-secret",
              id: "raw-id-secret",
              pk: 42,
              membership_id: "membership-secret",
              username: "reader",
              first_name: "Reader",
              last_name: "One",
              email: "reader@example.test",
            }};
            const defaultNode = renderUserIdentity(user);
            const managementNode = renderUserIdentity(user, {{ includeEmail: true }});
            process.stdout.write(JSON.stringify({{
              defaultText: userIdentityText(user),
              managementText: userIdentityText(user, {{ includeEmail: true }}),
              defaultRenderedText: defaultNode.textContent,
              managementRenderedText: managementNode.textContent,
              defaultHtml: defaultNode.outerHTML,
              managementHtml: managementNode.outerHTML,
            }}));
            """
        )

        for value in (
            result["defaultText"],
            result["defaultRenderedText"],
            result["defaultHtml"],
        ):
            assert "reader@example.test" not in value
            assert "profile-secret" not in value
            assert "raw-id-secret" not in value
            assert "membership-secret" not in value
            assert "42" not in value

        assert result["defaultText"] == "Reader One, <@reader>"
        assert result["defaultRenderedText"] == "personReader One<@reader>"
        assert result["managementText"] == "Reader One, <@reader>, reader@example.test"
        assert "reader@example.test" in result["managementRenderedText"]
        assert "reader@example.test" in result["managementHtml"]

    def test_render_user_identity_treats_malicious_identity_fields_as_text(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            import {{ renderUserIdentity }} from "./web/static/web/js/ui/identity.js";

            const user = {{
              username: "reader<img src=x onerror=alert(1)>",
              first_name: "<strong>Ada</strong>",
              last_name: "Lovelace<script>alert(1)</script>",
              email: "ada@example.test<script>alert(2)</script>",
            }};
            const node = renderUserIdentity(user, {{
              className: "extra",
              element: "div",
              includeEmail: true,
            }});
            process.stdout.write(JSON.stringify({{
              html: node.outerHTML,
              text: node.textContent,
              pieceCount: node.querySelectorAll(".user-identity__piece").length,
              className: node.className,
            }}));
            """
        )

        assert result["pieceCount"] == 3
        assert result["className"] == "user-identity extra"
        assert "<strong>" in result["text"]
        assert "<script>" in result["text"]
        assert "<img" in result["text"]
        assert "<strong>" not in result["html"]
        assert "<script>" not in result["html"]
        assert "<img" not in result["html"]
        assert "&lt;strong&gt;Ada&lt;/strong&gt;" in result["html"]
        assert "reader&lt;img src=x onerror=alert(1)&gt;" in result["html"]
