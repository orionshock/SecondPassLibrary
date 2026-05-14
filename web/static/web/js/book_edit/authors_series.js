import { clear, el } from "./shared.js";

export function renderSelectedAuthors({ selectedAuthors, authorsSelectedEl }) {
  clear(authorsSelectedEl);
  if (!selectedAuthors.length) {
    authorsSelectedEl.appendChild(el("div", "muted", "No authors."));
    return;
  }
  const ul = document.createElement("ul");
  for (const a of selectedAuthors) {
    const id = a && a.id != null ? String(a.id) : "";
    const name = a && a.name ? String(a.name) : id;
    const li = document.createElement("li");
    li.appendChild(document.createTextNode(name + " "));
    const muted = el("span", "muted");
    const code = document.createElement("code");
    code.textContent = id;
    muted.appendChild(code);
    li.appendChild(muted);
    li.appendChild(document.createTextNode(" "));
    const btn = el("button", "linklike", "Remove");
    btn.type = "button";
    btn.style.marginLeft = "8px";
    btn.setAttribute("data-remove-author-id", id);
    li.appendChild(btn);
    ul.appendChild(li);
  }
  authorsSelectedEl.appendChild(ul);
}

export function syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl }) {
  clear(authorAddSelectEl);
  const currentIds = new Set(selectedAuthors.map((a) => String(a.id)));
  const items = allAuthors
    .slice()
    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
    .filter((a) => a && a.id && !currentIds.has(String(a.id)))
    .slice(0, 500);
  if (!items.length) {
    const opt = document.createElement("option");
    opt.value = "";
    opt.textContent = "(No more authors)";
    authorAddSelectEl.appendChild(opt);
    authorAddBtnEl.disabled = true;
    return;
  }
  for (const a of items) {
    const opt = document.createElement("option");
    opt.value = String(a.id);
    opt.textContent = String(a.name || a.id);
    authorAddSelectEl.appendChild(opt);
  }
  authorAddBtnEl.disabled = false;
}

export function syncSeriesSelectOptions({ allSeries, seriesSelectEl, selectedId }) {
  clear(seriesSelectEl);
  const none = document.createElement("option");
  none.value = "";
  none.textContent = "(No series)";
  seriesSelectEl.appendChild(none);
  const items = allSeries
    .slice()
    .sort((a, b) => String(a.name || "").localeCompare(String(b.name || "")))
    .slice(0, 500);
  for (const s of items) {
    const opt = document.createElement("option");
    opt.value = String(s.id);
    opt.textContent = String(s.name || s.id);
    seriesSelectEl.appendChild(opt);
  }
  seriesSelectEl.value = selectedId || "";
}

