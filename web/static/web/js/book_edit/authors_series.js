import { clear, el } from "./shared.js";

function compareAuthors(a, b) {
  const aSort = String((a && a.sort_name) || (a && a.name) || "");
  const bSort = String((b && b.sort_name) || (b && b.name) || "");
  return aSort.localeCompare(bSort) || String((a && a.name) || "").localeCompare(String((b && b.name) || ""));
}

export function renderSelectedAuthors({ selectedAuthors, authorsSelectedEl }) {
  clear(authorsSelectedEl);
  if (!selectedAuthors.length) {
    authorsSelectedEl.appendChild(el("div", "muted", "No authors."));
    return;
  }
  const ul = document.createElement("ul");
  ul.className = "selected-author-list";
  for (const a of selectedAuthors.slice().sort(compareAuthors)) {
    const id = a && a.id != null ? String(a.id) : "";
    const name = a && a.name ? String(a.name) : id;
    const li = document.createElement("li");
    li.className = "selected-author-list__item";
    const btn = el("button", "icon-button icon-button--danger");
    btn.type = "button";
    btn.setAttribute("data-remove-author-id", id);
    btn.setAttribute("aria-label", `Remove ${name}`);
    btn.setAttribute("title", `Remove ${name}`);
    const icon = el("span", "material-symbols-outlined", "remove_circle");
    icon.setAttribute("aria-hidden", "true");
    btn.appendChild(icon);
    li.appendChild(btn);
    li.appendChild(document.createTextNode(name));
    ul.appendChild(li);
  }
  authorsSelectedEl.appendChild(ul);
}

export function syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl }) {
  clear(authorAddSelectEl);
  const currentIds = new Set(selectedAuthors.map((a) => String(a.id)));
  const items = allAuthors
    .slice()
    .sort(compareAuthors)
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
