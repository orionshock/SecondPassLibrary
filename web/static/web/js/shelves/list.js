import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { pagedController } from "./shared.js";

function renderShelfRow(s) {
  const id = s && s.id != null ? String(s.id) : "";
  const name = s && s.name ? String(s.name) : "(Unnamed shelf)";
  const desc = s && s.description ? String(s.description) : "";
  const ownerType = s && s.owner_type ? String(s.owner_type) : "";
  const visibility = s && s.visibility ? String(s.visibility) : "";

  let ownerLine = "";
  if (ownerType === "user" && s.owner_user) {
    ownerLine = `User: ${escapeHtml(s.owner_user.username || "user")}`;
  } else if (ownerType === "group" && s.owner_group) {
    ownerLine = `Group: ${escapeHtml(s.owner_group.name || "group")}`;
  }

  const visLine = ownerType === "user" ? ` Â· ${escapeHtml(visibility)}` : "";

  return `
    <article class="book">
      <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
        <div>
          <h3 class="book__title">
            <a href="/shelves/${encodeURIComponent(id)}/">${escapeHtml(name)}</a>
          </h3>
          ${desc ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(desc)}</div>` : ""}
          <div class="muted" style="margin-top: 4px;">${ownerLine}${visLine}</div>
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

  const ctl = await pagedController({
    statusEl,
    resultsEl,
    prevBtn,
    nextBtn,
    noteEl,
    initialUrl: "/api/v1/shelves/",
    renderRow: renderShelfRow,
    emptyText: "No visible shelves.",
  });

  visible(listEl, true);
  await ctl.loadFirst();
}
