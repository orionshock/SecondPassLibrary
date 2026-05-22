import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { inferCanEditShelf, setStatus } from "./shared.js";
import { initShelfItemsEditor } from "./items.js";
import { initShelfBookSearch } from "./book_search.js";

export async function initShelfEdit() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const statusEl = $("#shelf-edit-status");
  const errEl = $("#shelf-edit-error");
  const notAllowedEl = $("#shelf-edit-not-allowed");
  const tabsEl = $("#shelf-edit-tabs");
  const tabBooks = $("#shelf-edit-tab-books");
  const tabAdd = $("#shelf-edit-tab-add");
  const tabDetails = $("#shelf-edit-tab-details");
  const panelBooks = $("#shelf-edit-panel-books");
  const panelAdd = $("#shelf-edit-panel-add");
  const panelDetails = $("#shelf-edit-panel-details");
  const wrapEl = $("#shelf-edit");
  const formEl = $("#shelf-edit-form");
  const nameEl = $("#shelf-edit-name");
  const descEl = $("#shelf-edit-description");
  const visEl = $("#shelf-edit-visibility");
  const visNote = $("#shelf-edit-visibility-note");
  const visRowK = $("#shelf-edit-visibility-row");
  const visRowV = $("#shelf-edit-visibility-row-v");
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
  const ownerContextEl = $("#shelf-edit-owner-context");
  const visibilityContextEl = $("#shelf-edit-visibility-context");
  const itemCountEl = $("#shelf-edit-item-count");
  const groupLinkEl = $("#shelf-edit-group-link");
  const contextNoteEl = $("#shelf-edit-context-note");
  const addCard = $("#shelf-edit-add");
  const dangerCard = $("#shelf-edit-danger");
  const deleteBtn = $("#shelf-edit-delete-btn");
  const deleteStatus = $("#shelf-edit-delete-status");
  if (
    !statusEl ||
    !errEl ||
    !notAllowedEl ||
    !tabsEl ||
    !tabBooks ||
    !tabAdd ||
    !tabDetails ||
    !panelBooks ||
    !panelAdd ||
    !panelDetails ||
    !wrapEl ||
    !formEl ||
    !nameEl ||
    !descEl ||
    !visEl ||
    !visNote ||
    !visRowK ||
    !visRowV ||
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
    !titleEl ||
    !ownerContextEl ||
    !visibilityContextEl ||
    !itemCountEl ||
    !groupLinkEl ||
    !contextNoteEl ||
    !addCard ||
    !dangerCard ||
    !deleteBtn ||
    !deleteStatus
  )
    return;

  function setActiveTab(tabName) {
    const isBooks = tabName === "books";
    const isAdd = tabName === "add";
    const isDetails = tabName === "details";

    tabBooks.classList.toggle("is-active", isBooks);
    tabAdd.classList.toggle("is-active", isAdd);
    tabDetails.classList.toggle("is-active", isDetails);

    visible(panelBooks, isBooks);
    visible(panelAdd, isAdd);
    visible(panelDetails, isDetails);
  }

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
  visible(tabsEl, false);
  visible(panelBooks, false);
  visible(panelAdd, false);
  visible(panelDetails, false);
  visible(wrapEl, false);
  visible(itemsCard, false);
  visible(addCard, false);
  visible(dangerCard, false);
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

  const ownerType = shelf && shelf.owner_type ? String(shelf.owner_type) : "";
  const ownerUser = shelf && shelf.owner_user ? shelf.owner_user : null;
  const ownerGroup = shelf && shelf.owner_group ? shelf.owner_group : null;
  const ownerGroupId = ownerType === "group" && ownerGroup && ownerGroup.id ? String(ownerGroup.id) : "";

  titleEl.textContent = shelf && shelf.name ? String(shelf.name) : "Shelf";

  if (ownerType === "user") {
    const username = ownerUser && ownerUser.username ? String(ownerUser.username) : "user";
    ownerContextEl.textContent = `User shelf by ${username}`;
    const visibility = shelf && shelf.visibility ? String(shelf.visibility) : "private";
    visibilityContextEl.textContent = `Visibility: ${visibility}`;
    contextNoteEl.textContent =
      "User shelves do not grant book access. Books are shown only while you can access them. Listed shelves do not grant access.";
    visible(groupLinkEl, false);
  } else if (ownerType === "group") {
    const groupName = ownerGroup && ownerGroup.name ? String(ownerGroup.name) : "group";
    ownerContextEl.textContent = `Group shelf: ${groupName}`;
    visibilityContextEl.textContent = "";
    contextNoteEl.textContent = "Only books assigned to this group can be added.";
    if (ownerGroupId) {
      groupLinkEl.setAttribute("href", `/groups/${encodeURIComponent(String(ownerGroupId))}/`);
      visible(groupLinkEl, true);
    } else {
      visible(groupLinkEl, false);
    }
  } else {
    ownerContextEl.textContent = "";
    visibilityContextEl.textContent = "";
    contextNoteEl.textContent = "";
    visible(groupLinkEl, false);
  }

  const canEdit = shelf && shelf.can_edit != null ? !!shelf.can_edit : inferCanEditShelf({ me, shelf });
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
    visRowK.style.display = "";
    visRowV.style.display = "";
    visNote.textContent = "Group shelves are visible to group members only.";
  } else {
    visEl.disabled = false;
    visRowK.style.display = "";
    visRowV.style.display = "";
    visEl.value = shelf.visibility || "private";
    visNote.textContent = "Listed shelves are visible to authenticated users but do not grant book access.";
  }

  visible(tabsEl, true);
  setActiveTab("books");

  visible(wrapEl, true);
  visible(itemsCard, true);
  visible(addCard, true);
  visible(dangerCard, true);
  setStatus(statusEl, "", false);

  tabBooks.addEventListener("click", () => setActiveTab("books"));
  tabAdd.addEventListener("click", () => setActiveTab("add"));
  tabDetails.addEventListener("click", () => setActiveTab("details"));

  formEl.addEventListener("submit", async (e) => {
    e.preventDefault();
    setErr("");
    setGlobalError("");
    setStatus(saveStatus, "Saving...", false);
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

  const itemsCtl = await initShelfItemsEditor({
    shelfId,
    itemsStatus,
    itemsResults,
    prevBtn,
    nextBtn,
    noteEl,
    itemCountEl,
  });

  initShelfBookSearch({
    shelfId,
    ownerType,
    ownerGroupId,
    searchForm,
    searchInput,
    searchStatus,
    searchResults,
    getCurrentShelfBookIds: itemsCtl.getCurrentShelfBookIds,
    reloadItems: itemsCtl.reloadItems,
  });

  deleteBtn.addEventListener("click", async () => {
    const shelfName = shelf && shelf.name ? String(shelf.name) : "";
    const ok = window.confirm(`Delete shelf${shelfName ? ` "${shelfName}"` : ""}? This cannot be undone.`);
    if (!ok) return;

    setGlobalError("");
    setStatus(deleteStatus, "Deleting...", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      await fetchJSONWithOptions(`/api/v1/shelves/${encodeURIComponent(String(shelfId))}/`, { method: "DELETE", headers });
      window.location.href = "/shelves/";
    } catch (e2) {
      console.error("Failed to delete shelf", e2);
      setGlobalError(extractApiErrorMessage(e2));
      setStatus(deleteStatus, "", true);
    }
  });
}
