import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { createPagedListController } from "../ui/paged_list.js";
import { shelfMetadataLine } from "./shared.js";

function renderShelfRow(s) {
  const id = s && s.id != null ? String(s.id) : "";
  const name = s && s.name ? String(s.name) : "(Unnamed shelf)";
  const desc = s && s.description ? String(s.description) : "";
  const metaLine = shelfMetadataLine(s);

  return `
    <article class="book">
      <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
        <div>
          <h3 class="book__title">
            <a href="/shelves/${encodeURIComponent(id)}/">${escapeHtml(name)}</a>
          </h3>
          ${desc ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(desc)}</div>` : ""}
          ${metaLine ? `<div class="muted" style="margin-top: 4px;">${metaLine}</div>` : ""}
        </div>
      </div>
    </article>
  `.trim();
}

export async function initShelvesList() {
  await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelves-status");
  const listEl = $("#shelves-list");
  const resultsEl = $("#shelves-results");
  const prevBtn = $("#shelves-prev");
  const nextBtn = $("#shelves-next");
  const noteEl = $("#shelves-page-note");
  if (!statusEl || !listEl || !resultsEl) return;

  const ctl = await createPagedListController({
    statusEl,
    resultsEl,
    prevBtn,
    nextBtn,
    noteEl,
    initialUrl: "/api/v1/shelves/",
    emptyText: "No visible shelves.",
    autoLoad: false,
    clearResultsOnLoad: false,
    render: (payload, rows, emptyText) =>
      rows.length
        ? rows.map(renderShelfRow).join("")
        : `<div class="muted">${escapeHtml(emptyText)}</div>`,
    formatStatus: () => "",
    formatNote: (payload) =>
      payload && payload.count != null ? `${Number(payload.count)} total` : "",
  });

  visible(listEl, true);
  await ctl.loadFirst();
}
