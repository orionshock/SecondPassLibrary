import {
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  extractApiErrorMessage,
} from "./api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "./layout.js";

function setStatus(el, text, isError) {
  if (!el) return;
  el.textContent = text || "";
  el.classList.toggle("error", !!isError);
}

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

  const visLine = ownerType === "user" ? ` · ${escapeHtml(visibility)}` : "";

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

async function pagedController({ statusEl, resultsEl, prevBtn, nextBtn, noteEl, initialUrl, renderRow, emptyText }) {
  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = initialUrl;

  async function load(url) {
    setStatus(statusEl, "Loading…", false);
    const payload = await fetchJSON(url);
    const rows = Array.isArray(payload && payload.results) ? payload.results : [];
    resultsEl.innerHTML = rows.length ? rows.map(renderRow).join("") : `<div class="muted">${escapeHtml(emptyText)}</div>`;
    nextUrl = payload && payload.next ? String(payload.next) : null;
    prevUrl = payload && payload.previous ? String(payload.previous) : null;
    currentUrl = url;

    if (prevBtn) prevBtn.disabled = !prevUrl;
    if (nextBtn) nextBtn.disabled = !nextUrl;
    if (noteEl) {
      const count = payload && payload.count != null ? Number(payload.count) : null;
      noteEl.textContent = count != null ? `${count} total` : "";
    }

    setStatus(statusEl, "", false);
    return payload;
  }

  if (prevBtn) {
    prevBtn.addEventListener("click", () => {
      if (!prevUrl) return;
      load(prevUrl).catch((e) => {
        console.error("Pagination prev failed", e);
        setGlobalError(extractApiErrorMessage(e));
      });
    });
  }
  if (nextBtn) {
    nextBtn.addEventListener("click", () => {
      if (!nextUrl) return;
      load(nextUrl).catch((e) => {
        console.error("Pagination next failed", e);
        setGlobalError(extractApiErrorMessage(e));
      });
    });
  }

  return { loadFirst: () => load(initialUrl), reload: () => load(currentUrl) };
}

function inferCanEditShelf({ me, shelf }) {
  if (!me || !shelf) return false;
  if (shelf.owner_type === "user") return shelf.owner_user && String(shelf.owner_user.username) === String(me.username || "");

  // For group shelves, infer from role/capabilities:
  // - broad roles (owner/manager/librarian) can edit
  // - curator can edit non-Public group shelves if they are curator in that group
  const isOwner = !!me.is_owner;
  const role = me.role || "";
  const isBroad = isOwner || role === "manager" || role === "librarian";
  if (isBroad) return true;

  const og = shelf.owner_group;
  if (!og || og.is_public_group) return false;
  const groups = Array.isArray(me.groups) ? me.groups : [];
  const membership = groups.find((g) => g && String(g.id) === String(og.id));
  return membership && membership.membership_role === "curator";
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

export async function initShelfNew() {
  await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-new-status");
  const cardEl = $("#shelf-new-card");
  const errEl = $("#shelf-new-error");
  const formEl = $("#shelf-new-form");
  const nameEl = $("#shelf-new-name");
  const descEl = $("#shelf-new-description");
  const ownerTypeEl = $("#shelf-new-owner-type");
  const visibilityEl = $("#shelf-new-visibility");
  const ownerGroupEl = $("#shelf-new-owner-group");
  const submitStatusEl = $("#shelf-new-submit-status");
  if (!statusEl || !cardEl || !errEl || !formEl || !nameEl || !descEl || !ownerTypeEl || !visibilityEl || !ownerGroupEl) return;

  function setErr(msg) {
    errEl.textContent = msg || "";
    visible(errEl, !!msg);
  }

  setStatus(statusEl, "Loading…", false);
  setErr("");
  visible(cardEl, true);

  const groups = await fetchJSON("/api/v1/library/groups/");
  const results = Array.isArray(groups && groups.results) ? groups.results : [];
  ownerGroupEl.textContent = "";
  for (const g of results) {
    const opt = document.createElement("option");
    opt.value = String(g.id);
    opt.textContent = String(g.name || g.id);
    ownerGroupEl.appendChild(opt);
  }

  const qs = new URLSearchParams(window.location.search || "");
  const preOwnerType = qs.get("owner_type");
  const preOwnerGroup = qs.get("owner_group");
  if (preOwnerType === "group") ownerTypeEl.value = "group";
  if (preOwnerGroup) ownerGroupEl.value = preOwnerGroup;

  function syncOwnerUI() {
    const isGroup = ownerTypeEl.value === "group";
    visibilityEl.disabled = isGroup;
    ownerGroupEl.disabled = !isGroup;
    if (isGroup) visibilityEl.value = "private";
  }
  ownerTypeEl.addEventListener("change", syncOwnerUI);
  syncOwnerUI();

  setStatus(statusEl, "", false);

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    setErr("");
    setStatus(submitStatusEl, "Creating…", false);

    const body = {
      name: nameEl.value || "",
      description: descEl.value || "",
      owner_type: ownerTypeEl.value,
    };
    if (ownerTypeEl.value === "user") body.visibility = visibilityEl.value;
    if (ownerTypeEl.value === "group") body.owner_group = ownerGroupEl.value;

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const created = await fetchJSONWithOptions("/api/v1/shelves/", {
        method: "POST",
        headers,
        body: JSON.stringify(body),
      });

      setStatus(submitStatusEl, "", false);
      const id = created && created.id ? String(created.id) : "";
      window.location.href = id ? `/shelves/${encodeURIComponent(id)}/edit/` : "/shelves/";
    } catch (e2) {
      console.error("Failed to create shelf", e2);
      const msg = extractApiErrorMessage(e2);
      setErr(msg);
      setGlobalError(msg);
      setStatus(submitStatusEl, "", true);
    }
  });
}

function renderShelfMeta(container, shelf) {
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
    row("Owner", escapeHtml(shelf.owner_user.username || ""));
    row("Visibility", escapeHtml(shelf.visibility || ""));
  }
  if (shelf.owner_type === "group" && shelf.owner_group) {
    const gid = shelf.owner_group.id ? String(shelf.owner_group.id) : "";
    const gname = shelf.owner_group.name || gid;
    row("Owner group", `<a href="/groups/${encodeURIComponent(gid)}/">${escapeHtml(gname)}</a>`);
  }

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
      const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
      const series = b.series && b.series.name ? String(b.series.name) : "";
      const meta = [authors.length ? authors.join(", ") : "", series].filter(Boolean).join(" · ");
      return `
        <article class="book">
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

  setStatus(statusEl, "Loading…", false);
  setErr("");
  visible(wrapEl, false);
  visible(itemsCard, false);
  visible(editWrap, false);

  try {
    const shelf = await fetchJSON(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/`);
    titleEl.textContent = shelf && shelf.name ? String(shelf.name) : "Shelf";
    renderShelfMeta(metaEl, shelf);
    visible(wrapEl, true);

    const canEdit = inferCanEditShelf({ me, shelf });
    visible(editWrap, canEdit);
    if (canEdit) editLink.setAttribute("href", `/shelves/${encodeURIComponent(String(shelfId))}/edit/`);

    let nextUrl = null;
    let prevUrl = null;
    let currentUrl = `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`;

    async function loadItems(url) {
      setStatus(itemsStatus, "Loading…", false);
      const payload = await fetchJSON(url);
      itemsResults.innerHTML = renderShelfItems(payload);
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

export async function initShelfEdit() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-edit-status");
  const errEl = $("#shelf-edit-error");
  const notAllowedEl = $("#shelf-edit-not-allowed");
  const wrapEl = $("#shelf-edit");
  const formEl = $("#shelf-edit-form");
  const nameEl = $("#shelf-edit-name");
  const descEl = $("#shelf-edit-description");
  const visEl = $("#shelf-edit-visibility");
  const visNote = $("#shelf-edit-visibility-note");
  const saveStatus = $("#shelf-edit-save-status");
  const itemsCard = $("#shelf-edit-items");
  const itemsStatus = $("#shelf-edit-items-status");
  const itemsResults = $("#shelf-edit-items-results");
  const prevBtn = $("#shelf-edit-items-prev");
  const nextBtn = $("#shelf-edit-items-next");
  const noteEl = $("#shelf-edit-items-page-note");
  const searchForm = $("#shelf-edit-book-search-form");
  const searchInput = $("#shelf-edit-book-search-input");
  const searchStatus = $("#shelf-edit-book-search-status");
  const searchResults = $("#shelf-edit-book-search-results");
  const titleEl = $("#shelf-edit-title");
  if (
    !statusEl ||
    !errEl ||
    !notAllowedEl ||
    !wrapEl ||
    !formEl ||
    !nameEl ||
    !descEl ||
    !visEl ||
    !visNote ||
    !saveStatus ||
    !itemsCard ||
    !itemsStatus ||
    !itemsResults ||
    !prevBtn ||
    !nextBtn ||
    !noteEl ||
    !searchForm ||
    !searchInput ||
    !searchStatus ||
    !searchResults ||
    !titleEl
  )
    return;

  function setErr(msg) {
    errEl.textContent = msg || "";
    visible(errEl, !!msg);
  }

  const shelfId = wrapEl.dataset ? wrapEl.dataset.shelfId : "";
  if (!shelfId) {
    setStatus(statusEl, "Missing shelf id.", true);
    return;
  }

  setStatus(statusEl, "Loading…", false);
  setErr("");
  visible(wrapEl, false);
  visible(itemsCard, false);
  visible(notAllowedEl, false);

  let shelf = null;
  try {
    shelf = await fetchJSON(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/`);
  } catch (e) {
    console.error("Failed to load shelf", e);
    const msg = e && e.status === 404 ? "Shelf not found or not accessible." : extractApiErrorMessage(e);
    setErr(msg);
    setGlobalError(msg);
    setStatus(statusEl, "Error.", true);
    return;
  }

  titleEl.textContent = shelf && shelf.name ? `Edit: ${shelf.name}` : "Edit shelf";
  const canEdit = inferCanEditShelf({ me, shelf });
  if (!canEdit) {
    visible(notAllowedEl, true);
    setStatus(statusEl, "", false);
    return;
  }

  nameEl.value = shelf.name || "";
  descEl.value = shelf.description || "";

  if (shelf.owner_type === "group") {
    visEl.value = "private";
    visEl.disabled = true;
    visNote.textContent = "Group-owned shelves are always private.";
  } else {
    visEl.disabled = false;
    visEl.value = shelf.visibility || "private";
    visNote.textContent = "Listed shelves are visible to authenticated users but do not grant book access.";
  }

  visible(wrapEl, true);
  visible(itemsCard, true);
  setStatus(statusEl, "", false);

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    setErr("");
    setGlobalError("");
    setStatus(saveStatus, "Saving…", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      const patch = { name: nameEl.value || "", description: descEl.value || "" };
      if (shelf.owner_type === "user") patch.visibility = visEl.value;

      shelf = await fetchJSONWithOptions(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/`, {
        method: "PATCH",
        headers,
        body: JSON.stringify(patch),
      });
      setStatus(saveStatus, "Saved.", false);
      window.setTimeout(() => setStatus(saveStatus, "", false), 1200);
    } catch (e2) {
      console.error("Failed to save shelf", e2);
      const msg = extractApiErrorMessage(e2);
      setErr(msg);
      setGlobalError(msg);
      setStatus(saveStatus, "", true);
    }
  });

  async function loadItems(url) {
    setStatus(itemsStatus, "Loading…", false);
    const payload = await fetchJSON(url);
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (!results.length) itemsResults.innerHTML = `<div class="muted">No books.</div>`;
    else {
      itemsResults.innerHTML = results
        .map((it) => {
          const b = it.book || {};
          const bid = b.id ? String(b.id) : "";
          const title = b.title ? String(b.title) : "(Untitled)";
          const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
          const series = b.series && b.series.name ? String(b.series.name) : "";
          const meta = [authors.length ? authors.join(", ") : "", series].filter(Boolean).join(" · ");
          return `
            <article class="book">
              <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
                <div style="flex: 1;">
                  <h3 class="book__title">
                    <a href="/library/books/${encodeURIComponent(bid)}/">${escapeHtml(title)}</a>
                  </h3>
                  ${meta ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(meta)}</div>` : ""}
                  <div class="muted" style="margin-top: 6px; display:flex; gap: 10px; align-items:center; flex-wrap: wrap;">
                    <label class="muted">Position</label>
                    <input type="number" value="${escapeHtml(it.position)}" style="width: 110px;" data-action="pos" data-item-id="${escapeHtml(
                      it.id
                    )}" />
                    <button class="button" type="button" data-action="save-pos" data-item-id="${escapeHtml(it.id)}">Save position</button>
                    <button class="button" type="button" data-action="remove-item" data-item-id="${escapeHtml(it.id)}">Remove</button>
                  </div>
                </div>
              </div>
            </article>
          `.trim();
        })
        .join("");
    }
    prevBtn.disabled = !payload.previous;
    nextBtn.disabled = !payload.next;
    noteEl.textContent = payload.count != null ? `${payload.count} total` : "";
    setStatus(itemsStatus, "", false);
    return payload;
  }

  let itemsNext = null;
  let itemsPrev = null;
  let currentItemsUrl = `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`;
  let currentShelfBookIds = new Set();

  async function reloadItems() {
    const payload = await loadItems(currentItemsUrl);
    itemsNext = payload.next ? String(payload.next) : null;
    itemsPrev = payload.previous ? String(payload.previous) : null;
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    currentShelfBookIds = new Set(results.map((it) => (it && it.book && it.book.id != null ? String(it.book.id) : "")).filter(Boolean));
  }

  prevBtn.addEventListener("click", () => {
    if (!itemsPrev) return;
    currentItemsUrl = itemsPrev;
    reloadItems().catch((e) => setGlobalError(extractApiErrorMessage(e)));
  });
  nextBtn.addEventListener("click", () => {
    if (!itemsNext) return;
    currentItemsUrl = itemsNext;
    reloadItems().catch((e) => setGlobalError(extractApiErrorMessage(e)));
  });

  await reloadItems();

  itemsResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    const action = target.getAttribute("data-action");
    const itemId = target.getAttribute("data-item-id");
    if (!action || !itemId) return;

    if (action === "remove-item") {
      setGlobalError("");
      setStatus(itemsStatus, "Removing…", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;
        await fetchJSONWithOptions(
          `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
          { method: "DELETE", headers }
        );
        await reloadItems();
      } catch (e2) {
        console.error("Failed to remove shelf item", e2);
        setGlobalError(extractApiErrorMessage(e2));
        setStatus(itemsStatus, "", true);
      }
    }

    if (action === "save-pos") {
      const input = itemsResults.querySelector(`input[data-action="pos"][data-item-id="${itemId}"]`);
      const position = input ? Number(input.value) : 0;
      setGlobalError("");
      setStatus(itemsStatus, "Saving…", false);
      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;
        await fetchJSONWithOptions(
          `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
          { method: "PATCH", headers, body: JSON.stringify({ position }) }
        );
        await reloadItems();
      } catch (e2) {
        console.error("Failed to save position", e2);
        setGlobalError(extractApiErrorMessage(e2));
        setStatus(itemsStatus, "", true);
      }
    }
  });

  async function runBookSearch(term) {
    if (!term) {
      searchResults.innerHTML = "";
      return;
    }
    setStatus(searchStatus, "Searching…", false);
    const payload = await fetchJSON(`/api/v1/library/books/?q=${encodeURIComponent(term)}`);
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    const filtered = results.filter((b) => {
      const bid = b && b.id != null ? String(b.id) : "";
      return bid && !currentShelfBookIds.has(bid);
    });

    if (!filtered.length) {
      searchResults.innerHTML = `<div class="muted">No results.</div>`;
      setStatus(searchStatus, "", false);
      return;
    }

    searchResults.innerHTML = filtered
      .map((b) => {
        const bid = b.id ? String(b.id) : "";
        const title = b.title ? String(b.title) : "(Untitled)";
        const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
        const series = b.series && b.series.name ? String(b.series.name) : "";
        const meta = [authors.length ? authors.join(", ") : "", series].filter(Boolean).join(" · ");
        return `
          <article class="book">
            <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
              <div style="flex: 1;">
                <h3 class="book__title">${escapeHtml(title)}</h3>
                ${meta ? `<div class="muted" style="margin-top: 4px;">${escapeHtml(meta)}</div>` : ""}
              </div>
              <div>
                <button class="button" type="button" data-action="add-book" data-book-id="${escapeHtml(bid)}">Add</button>
              </div>
            </div>
          </article>
        `.trim();
      })
      .join("");

    setStatus(searchStatus, "", false);
  }

  searchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setGlobalError("");
    try {
      await runBookSearch(searchInput.value || "");
    } catch (e2) {
      console.error("Search failed", e2);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  searchResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    const action = target.getAttribute("data-action");
    const bookId = target.getAttribute("data-book-id");
    if (action !== "add-book" || !bookId) return;

    setGlobalError("");
    setStatus(searchStatus, "Adding…", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      await fetchJSONWithOptions(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ book: bookId }),
      });
      setStatus(searchStatus, "Added.", false);
      await reloadItems();
      await runBookSearch(searchInput.value || "");
      window.setTimeout(() => setStatus(searchStatus, "", false), 900);
    } catch (e2) {
      console.error("Failed to add book to shelf", e2);
      setGlobalError(extractApiErrorMessage(e2));
      setStatus(searchStatus, "", true);
    }
  });
}
