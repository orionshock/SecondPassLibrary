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
  constructor(tag, id = "") {
    this.nodeType = 1;
    this.tagName = tag;
    this.id = id;
    this.children = [];
    this.attributes = {};
    this.style = {};
    this._className = "";
    this._textContent = "";
    this._innerHTML = "";
    this.disabled = false;
    this.dataset = new Proxy({}, {
      set: (target, key, value) => {
        target[key] = String(value);
        this.attributes[dataAttributeName(key)] = String(value);
        return true;
      },
    });
    this.classList = {
      toggle: (name, force) => {
        const classes = new Set(this._className.split(/\s+/).filter(Boolean));
        const on = force === undefined ? !classes.has(name) : !!force;
        if (on) classes.add(name);
        else classes.delete(name);
        this._className = Array.from(classes).join(" ");
      },
      add: (...names) => {
        const classes = new Set(this._className.split(/\s+/).filter(Boolean));
        for (const name of names) classes.add(String(name));
        this._className = Array.from(classes).join(" ");
      },
    };
  }
  set className(value) { this._className = String(value || ""); }
  get className() { return this._className; }
  set textContent(value) { this._textContent = String(value); this.children = []; this._innerHTML = ""; }
  get textContent() {
    return this._textContent + this.children.map((child) => child.textContent).join("");
  }
  set innerHTML(value) { this._innerHTML = String(value); this.children = []; this._textContent = ""; }
  get innerHTML() {
    return this._innerHTML + this.children.map((child) => child.outerHTML).join("");
  }
  get childNodes() { return this.children; }
  get firstChild() { return this.children[0] || null; }
  set href(value) { this.attributes.href = String(value); }
  get href() { return this.attributes.href || ""; }
  set src(value) { this.attributes.src = String(value); }
  get src() { return this.attributes.src || ""; }
  set alt(value) { this.attributes.alt = String(value); }
  get alt() { return this.attributes.alt || ""; }
  set loading(value) { this.attributes.loading = String(value); }
  get loading() { return this.attributes.loading || ""; }
  setAttribute(name, value) { this.attributes[String(name)] = String(value); }
  getAttribute(name) { return this.attributes[String(name)] || null; }
  addEventListener() {}
  appendChild(child) {
    if (child && child.isFragment) {
      this.children.push(...child.children);
      return child;
    }
    this.children.push(child);
    return child;
  }
  removeChild(child) {
    this.children = this.children.filter((candidate) => candidate !== child);
    return child;
  }
  replaceChildren(...children) {
    this.children = [];
    this._innerHTML = "";
    this._textContent = "";
    for (const child of children) this.appendChild(child);
  }
  querySelectorAll(selector) {
    const matches = [];
    const visit = (node) => {
      if (!node || node.isFragment) {
        for (const child of node.children || []) visit(child);
        return;
      }
      if (selector === "[data-cover-url]" && node.attributes["data-cover-url"] != null) matches.push(node);
      if (selector.startsWith(".") && (node.className || "").split(/\s+/).includes(selector.slice(1))) matches.push(node);
      for (const child of node.children || []) visit(child);
    };
    visit(this);
    return matches;
  }
  get outerHTML() {
    const attrs = [];
    if (this.id) attrs.push(`id="${escapeHtml(this.id)}"`);
    if (this.className) attrs.push(`class="${escapeHtml(this.className)}"`);
    for (const [name, value] of Object.entries(this.attributes)) {
      attrs.push(`${escapeHtml(name)}="${escapeHtml(value)}"`);
    }
    if (this.disabled) attrs.push("disabled");
    const attrText = attrs.length ? ` ${attrs.join(" ")}` : "";
    const content = this._innerHTML || escapeHtml(this._textContent) + this.children.map((child) => child.outerHTML).join("");
    return `<${this.tagName}${attrText}>${content}</${this.tagName}>`;
  }
}

class TestFragment {
  constructor() {
    this.isFragment = true;
    this.children = [];
  }
  appendChild(child) {
    this.children.push(child);
    return child;
  }
}

const elements = new Map();
function element(id, tag = "div") {
  const node = new TestElement(tag, id);
  elements.set(`#${id}`, node);
  return node;
}

globalThis.window = {
  location: { pathname: "/shelves/shelf-1/", search: "" },
  addEventListener() {},
  history: { pushState() {}, replaceState() {} },
};
globalThis.document = {
  body: { dataset: { advancedLibraryGroups: "true" } },
  cookie: "",
  createElement(tag) { return new TestElement(String(tag)); },
  createDocumentFragment() { return new TestFragment(); },
  querySelector(selector) { return elements.get(selector) || null; },
};
globalThis.Element = TestElement;
"""


FETCH_FIXTURE = r"""
function jsonResponse(body, status = 200) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => "application/json" },
    json: async () => body,
    text: async () => JSON.stringify(body),
  };
}
"""


class ShelfItemRenderingJavaScriptTests:
    def test_shelf_view_renders_visible_items_safely_without_file_metadata(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            {FETCH_FIXTURE}
            [
              "ui-global-error",
              "shelf-view-status",
              "shelf-view-error",
              "shelf-view",
              "shelf-view-summary",
              "shelf-view-description",
              "shelf-view-created-by",
              "shelf-view-items",
              "shelf-view-items-status",
              "shelf-view-items-results",
              "shelf-view-items-prev-top",
              "shelf-view-items-prev-bottom",
              "shelf-view-items-next-top",
              "shelf-view-items-next-bottom",
              "shelf-view-items-page-size-top",
              "shelf-view-items-page-size-bottom",
              "shelf-view-items-range-top",
              "shelf-view-items-range-bottom",
              "shelf-view-items-pager-top",
              "shelf-view-items-pager-bottom",
              "shelf-title",
              "shelf-view-edit-wrap",
              "shelf-view-edit-link",
            ].forEach((id) => element(id));
            elements.get("#shelf-view").dataset.shelfId = "shelf-1";

            const calls = [];
            globalThis.fetch = async (url) => {{
              calls.push(String(url));
              if (url === "/api/v1/accounts/me/") return jsonResponse({{ username: "reader" }});
              if (url === "/api/v1/shelves/shelf-1/") return jsonResponse({{
                id: "shelf-1",
                name: "Reader Shelf",
                owner_type: "user",
                visibility: "listed",
                item_count: 1,
                created_by: {{ username: "creator", email: "creator@example.test" }},
                can_edit: false,
              }});
              if (url === "/api/v1/shelves/shelf-1/items/?page_size=20") return jsonResponse({{
                count: 1,
                next: null,
                previous: null,
                results: [{{
                  id: "item-secret",
                  position: 0,
                  added_by: {{ username: "adder", email: "adder@example.test" }},
                  book: {{
                    id: "book id/one",
                    title: "<img src=x onerror=alert(1)>",
                    cover_url: "/media/covers/cover.webp",
                    authors: [{{ name: "Author <script>alert(2)</script>" }}],
                    series: {{ name: "Series <b>Bad</b>" }},
                    source_filename: "private-source.epub",
                    checksum: "checksum-secret",
                    download_url: "/api/v1/library/books/book-id/download/",
                    book_file: "userdata/media/books/private.epub",
                    storage_path: "userdata/media/books/private.epub",
                  }},
                }}],
              }});
              throw new Error(`Unexpected fetch ${{url}}`);
            }};

            const {{ initShelfView }} = await import("./web/static/web/js/shelves/view.js");
            await initShelfView();

            const html = elements.get("#shelf-view-items-results").outerHTML;
            process.stdout.write(JSON.stringify({{
              calls,
              html,
              text: elements.get("#shelf-view-items-results").textContent,
              note: elements.get("#shelf-view-items-range-bottom").textContent,
              title: elements.get("#shelf-title").textContent,
            }}));
            """
        )

        html = result["html"]
        assert result["calls"] == [
            "/api/v1/accounts/me/",
            "/api/v1/shelves/shelf-1/",
            "/api/v1/shelves/shelf-1/items/?page_size=20",
        ]
        assert result["title"] == "Reader Shelf"
        assert result["note"] == "Showing 1-1 of 1"
        assert 'href="/library/books/book%20id%2Fone/"' in html
        assert "&lt;img src=x onerror=alert(1)&gt;" in html
        assert "Author &lt;script&gt;alert(2)&lt;/script&gt;" in html
        assert "Series &lt;b&gt;Bad&lt;/b&gt;" in html
        assert "<script>" not in html
        assert "<img src=x" not in html
        assert "<b>Bad</b>" not in html
        assert "private-source.epub" not in html
        assert "checksum-secret" not in html
        assert "download_url" not in html
        assert "/download/" not in html
        assert "userdata/media/books/private.epub" not in html
        assert "adder@example.test" not in html
        assert "item-secret" not in html

    def test_shelf_edit_item_rows_render_controls_positions_and_safe_book_metadata(self):
        result = run_node_json(
            f"""
            {DOM_FIXTURE}
            {FETCH_FIXTURE}
            const itemsStatus = element("items-status");
            const itemsResults = element("items-results");
            const prevButtons = [element("prev-top", "button"), element("prev-bottom", "button")];
            const nextButtons = [element("next-top", "button"), element("next-bottom", "button")];
            const pageSizeSelects = [element("size-top", "select"), element("size-bottom", "select")];
            const rangeEls = [element("range-top"), element("range-bottom")];
            const pagers = [element("pager-top"), element("pager-bottom")];
            const itemCountEl = element("item-count");

            const pagePayload = {{
              count: 2,
              next: null,
              previous: null,
              results: [{{
                id: "item-1",
                position: 0,
                book: {{
                  id: "book/id-1",
                  title: "<strong>Visible</strong>",
                  cover_url: "/media/covers/visible.webp",
                  authors: [{{ name: "Ada <script>alert(1)</script>" }}],
                  series: {{ name: "Series <img src=x onerror=alert(2)>" }},
                  source_filename: "private-source.epub",
                  checksum: "checksum-secret",
                  download_url: "/api/v1/library/books/book-id/download/",
                  storage_path: "userdata/media/books/private.epub",
                }},
              }}],
            }};
            const calls = [];
            globalThis.fetch = async (url) => {{
              calls.push(String(url));
              if (String(url).startsWith("/api/v1/shelves/shelf-1/items/")) return jsonResponse(pagePayload);
              throw new Error(`Unexpected fetch ${{url}}`);
            }};

            const {{ initShelfItemsEditor }} = await import("./web/static/web/js/shelves/items.js");
            const controller = await initShelfItemsEditor({{
              shelfId: "shelf-1",
              itemsStatus,
              itemsResults,
              prevButtons,
              nextButtons,
              pageSizeSelects,
              rangeEls,
              pagers,
              itemCountEl,
            }});

            process.stdout.write(JSON.stringify({{
              calls,
              html: itemsResults.innerHTML,
              note: rangeEls[1].textContent,
              itemCount: itemCountEl.textContent,
              prevDisabled: prevButtons[1].disabled,
              nextDisabled: nextButtons[1].disabled,
              currentIds: Array.from(controller.getCurrentShelfBookIds()),
            }}));
            """
        )

        html = result["html"]
        assert result["calls"] == [
            "/api/v1/shelves/shelf-1/items/?page_size=20",
            "/api/v1/shelves/shelf-1/items/",
        ]
        assert 'href="/library/books/book%2Fid-1/"' in html
        assert "&lt;strong&gt;Visible&lt;/strong&gt;" in html
        assert "Ada &lt;script&gt;alert(1)&lt;/script&gt;" in html
        assert "Series &lt;img src=x onerror=alert(2)&gt;" in html
        assert "<strong>Visible</strong>" not in html
        assert "<script>" not in html
        assert "<img src=x" not in html
        assert 'data-action="move-up"' in html
        assert 'data-action="move-down"' in html
        assert 'data-action="move-to"' in html
        assert 'data-action="remove-item"' in html
        assert 'data-item-id="item-1"' in html
        assert "#1" in html
        assert "Move up" in html
        assert "Move down" in html
        assert "Remove" in html
        assert "private-source.epub" not in html
        assert "checksum-secret" not in html
        assert "download_url" not in html
        assert "/download/" not in html
        assert "userdata/media/books/private.epub" not in html
        assert result["note"] == "Showing 1-1 of 2"
        assert result["itemCount"] == "Items: 2"
        assert result["prevDisabled"] is True
        assert result["nextDisabled"] is True
        assert result["currentIds"] == ["book/id-1"]
