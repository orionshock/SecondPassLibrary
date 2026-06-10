import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { inferCanEditShelf, shelfCreatedByDisplay, shelfOwnerDisplay, setStatus } from "./shared.js";
import { mountCovers } from "../ui/covers.js";

function renderShelfMeta(container, shelf, me) {
  container.innerHTML = "";
  const kv = document.createElement("div");
  kv.className = "kv";

  function row(k, v) {
    const kk = document.createElement("div");
    kk.className = "kv__k";
    kk.textContent = k;
    const vv = document.createElement("div");
    vv.className = "kv__v";
    vv.innerHTML = v;
    kv.appendChild(kk);
    kv.appendChild(vv);
  }

  row("Name", escapeHtml(shelf.name || ""));
  if (shelf.description) row("Description", escapeHtml(shelf.description));
  row("Owner type", escapeHtml(shelf.owner_type || ""));
  if (shelf.owner_type === "user" && shelf.owner_user) {
    row("Owner", escapeHtml(shelfOwnerDisplay(shelf, me) || ""));
    row("Visibility", escapeHtml(shelf.visibility || ""));
  }
  if (shelf.owner_type === "group" && shelf.owner_group) {
    const gid = shelf.owner_group.id ? String(shelf.owner_group.id) : "";
    const gname = shelf.owner_group.name || gid;
    row("Owner", `<a href="/groups/${encodeURIComponent(gid)}/">${escapeHtml(shelfOwnerDisplay(shelf, me) || gname)}</a>`);
  }
  const createdBy = shelfCreatedByDisplay(shelf);
  if (createdBy) row("Created by", escapeHtml(createdBy.replace(/^Created by /, "")));

  container.appendChild(kv);
}

function renderShelfItems(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (!results.length) return `<div class="muted">No visible books.</div>`;
  return results
    .map((it) => {
      const b = it.book || {};
      const bid = b.id ? String(b.id) : "";
      const title = b.title ? String(b.title) : "(Untitled)";
      const coverUrl = b.cover_url ? String(b.cover_url) : "";
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
      const series = b.series && b.series.name ? String(b.series.name) : "";
      const meta = [authors.length ? authors.join(", ") : "", series].filter(Boolean).join("  -  ");
      return `
        <article class="book book--with-cover">
          <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div>
              <h3 class="book__title">
                <a href="/library/books/${encodeURIComponent(bid)}/">${escapeHtml(title)}</a>
              </h3>
              ${meta ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(meta)}</div>` : ""}
            </div>
          </div>
        </article>
      `.trim();
    })
    .join("");
}

export async function initShelfView() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-view-status");
  const errEl = $("#shelf-view-error");
  const wrapEl = $("#shelf-view");
  const metaEl = $("#shelf-view-meta");
  const itemsCard = $("#shelf-view-items");
  const itemsStatus = $("#shelf-view-items-status");
  const itemsResults = $("#shelf-view-items-results");
  const prevBtn = $("#shelf-view-items-prev");
  const nextBtn = $("#shelf-view-items-next");
  const noteEl = $("#shelf-view-items-page-note");
  const titleEl = $("#shelf-title");
  const editWrap = $("#shelf-view-edit-wrap");
  const editLink = $("#shelf-view-edit-link");
  if (!statusEl || !errEl || !wrapEl || !metaEl || !itemsCard || !itemsStatus || !itemsResults || !titleEl || !editWrap || !editLink) return;

  function setErr(msg) {
    errEl.textContent = msg || "";
    visible(errEl, !!msg);
  }

  const shelfId = wrapEl.dataset ? wrapEl.dataset.shelfId : "";
  if (!shelfId) {
    setStatus(statusEl, "Missing shelf id.", true);
    return;
  }

  setStatus(statusEl, "Loading...", false);
  setErr("");
  visible(wrapEl, false);
  visible(itemsCard, false);
  visible(editWrap, false);

  try {
    const shelf = await fetchJSON(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/`);
    titleEl.textContent = shelf && shelf.name ? String(shelf.name) : "Shelf";
    renderShelfMeta(metaEl, shelf, me);
    visible(wrapEl, true);

    const canEdit = shelf && shelf.can_edit != null ? !!shelf.can_edit : inferCanEditShelf({ me, shelf });
    visible(editWrap, canEdit);
    if (canEdit) editLink.setAttribute("href", `/shelves/${encodeURIComponent(String(shelfId))}/edit/`);

    let nextUrl = null;
    let prevUrl = null;
    let currentUrl = `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`;

    async function loadItems(url) {
      setStatus(itemsStatus, "Loading...", false);
      const payload = await fetchJSON(url);
      itemsResults.innerHTML = renderShelfItems(payload);
      mountCovers(itemsResults);
      nextUrl = payload && payload.next ? String(payload.next) : null;
      prevUrl = payload && payload.previous ? String(payload.previous) : null;
      prevBtn.disabled = !prevUrl;
      nextBtn.disabled = !nextUrl;
      noteEl.textContent = payload && payload.count != null ? `${payload.count} total` : "";
      visible(itemsCard, true);
      setStatus(itemsStatus, "", false);
    }

    prevBtn.addEventListener("click", () => {
      if (!prevUrl) return;
      currentUrl = prevUrl;
      loadItems(currentUrl).catch((e) => setGlobalError(extractApiErrorMessage(e)));
    });
    nextBtn.addEventListener("click", () => {
      if (!nextUrl) return;
      currentUrl = nextUrl;
      loadItems(currentUrl).catch((e) => setGlobalError(extractApiErrorMessage(e)));
    });

    await loadItems(currentUrl);

    setStatus(statusEl, "", false);
  } catch (e) {
    console.error("Failed to load shelf view", { shelfId, e });
    const msg = e && e.status === 404 ? "Shelf not found or not accessible." : extractApiErrorMessage(e);
    setErr(msg);
    setStatus(statusEl, "Error.", true);
    setGlobalError(msg);
  }
}
