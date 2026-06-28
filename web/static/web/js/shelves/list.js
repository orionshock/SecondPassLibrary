import { $, escapeHtml, loadMeAndInitShell, setGlobalError } from "../layout.js";
import { renderCoverPreviewStrip } from "../ui/cover_previews.js";
import { createPagedListController } from "../ui/paged_list.js";
import { shelfMetadataLine } from "./shared.js";

function renderShelfRow(shelf) {
  const id = shelf && shelf.id != null ? String(shelf.id) : "";
  const name = shelf && shelf.name ? String(shelf.name) : "(Unnamed shelf)";
  const description = shelf && shelf.description ? String(shelf.description) : "";
  const metadata = shelfMetadataLine(shelf);
  const href = `/shelves/${encodeURIComponent(id)}/`;
  const previews = renderCoverPreviewStrip(shelf.preview_books, {
    href,
    actionLabel: `View shelf ${name}`,
  });

  return `
    <article class="book shelf-list-card">
      <h3 class="book__title">
        <a href="${escapeHtml(href)}">${escapeHtml(name)}</a>
      </h3>
      ${description ? `<div class="muted shelf-list-card__description">${escapeHtml(description)}</div>` : ""}
      ${metadata ? `<div class="muted shelf-list-card__metadata">${metadata}</div>` : ""}
      ${previews}
    </article>
  `.trim();
}

function renderShelfRows(_payload, rows, emptyText) {
  if (!rows.length) return `<div class="muted">${escapeHtml(emptyText)}</div>`;
  return rows.map(renderShelfRow).join("");
}

function pageNote(payload, rows) {
  if (!payload || payload.count == null) return "";
  return `Showing ${rows.length} of ${Number(payload.count)}.`;
}

async function createShelfSectionController({
  statusEl,
  resultsEl,
  prevBtn,
  nextBtn,
  noteEl,
  initialUrl,
  emptyText,
}) {
  return createPagedListController({
    statusEl,
    resultsEl,
    prevBtn,
    nextBtn,
    noteEl,
    initialUrl,
    emptyText,
    autoLoad: false,
    clearResultsOnLoad: false,
    render: renderShelfRows,
    formatStatus: () => "",
    formatNote: pageNote,
  });
}

export async function initShelvesList() {
  await loadMeAndInitShell();
  setGlobalError("");

  const personal = {
    statusEl: $("#personal-shelves-status"),
    resultsEl: $("#personal-shelves-results"),
    prevBtn: $("#personal-shelves-prev"),
    nextBtn: $("#personal-shelves-next"),
    noteEl: $("#personal-shelves-page-note"),
  };
  const shared = {
    statusEl: $("#shared-shelves-status"),
    resultsEl: $("#shared-shelves-results"),
    prevBtn: $("#shared-shelves-prev"),
    nextBtn: $("#shared-shelves-next"),
    noteEl: $("#shared-shelves-page-note"),
  };
  if (
    Object.values(personal).some((element) => !element) ||
    Object.values(shared).some((element) => !element)
  ) {
    return;
  }

  const [personalController, sharedController] = await Promise.all([
    createShelfSectionController({
      ...personal,
      initialUrl: "/api/v1/shelves/?scope=personal&include_preview_books=true",
      emptyText: "No personal shelves.",
    }),
    createShelfSectionController({
      ...shared,
      initialUrl: "/api/v1/shelves/?scope=shared&include_preview_books=true",
      emptyText: "No shared shelves.",
    }),
  ]);

  await Promise.all([
    personalController.loadFirst(),
    sharedController.loadFirst(),
  ]);
}
