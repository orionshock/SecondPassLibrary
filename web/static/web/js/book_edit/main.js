import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalErrorFromError, setText, visible } from "../layout.js";
import { fetchAllPages, setInlineStatus, uniqueById } from "./shared.js";
import { initTabs } from "./tabs.js";
import { applyBookToMetadataForm, buildBookPatchPayload } from "./metadata.js";
import { renderSelectedAuthors, syncAuthorSelectOptions, syncSeriesSelectOptions } from "./authors_series.js";
import { renderGroups, syncGroupsAddOptions } from "./groups.js";
import { renderHeader, renderFileInfo, renderIdentifiersTable } from "./identifiers_file.js";
import { refreshShelvesContext } from "./shelves.js";
import { mountCovers } from "../ui/covers.js";

export async function initBookEdit() {
  const me = await loadMeAndInitShell();
  initTabs();

  const headerEl = $("#book-edit-header");
  const headerTitleEl = $("#book-edit-header-title");
  const headerAuthorsEl = $("#book-edit-header-authors");
  const headerSeriesEl = $("#book-edit-header-series");
  const headerFileEl = $("#book-edit-header-file");
  const headerCoverEl = headerEl ? headerEl.querySelector(".edit-header__cover") : null;

  const rootEl = $("#book-edit");
  const statusEl = $("#book-edit-status");
  const errorEl = $("#book-edit-error");
  const savedEl = $("#book-edit-saved");
  const saveStatusEl = $("#book-edit-save-status");
  const formEl = $("#book-edit-form");
  const saveBtn = $("#book-edit-save");

  const titleEl = $("#book-edit-title");
  const subtitleEl = $("#book-edit-subtitle");
  const summaryEl = $("#book-edit-summary");
  const publisherEl = $("#book-edit-publisher");
  const languageEl = $("#book-edit-language");
  const publishedDateEl = $("#book-edit-published-date");
  const isbnEl = $("#book-edit-isbn");
  const subjectsEl = $("#book-edit-subjects");

  const authorsSelectedEl = $("#book-edit-authors-selected");
  const authorsStatusEl = $("#book-edit-authors-status");
  const authorAddSelectEl = $("#book-edit-author-add-select");
  const authorAddBtnEl = $("#book-edit-author-add-btn");
  const authorNewNameEl = $("#book-edit-author-new-name");
  const authorNewBtnEl = $("#book-edit-author-new-btn");

  const seriesSelectEl = $("#book-edit-series-select");
  const seriesStatusEl = $("#book-edit-series-status");
  const seriesNewNameEl = $("#book-edit-series-new-name");
  const seriesNewBtnEl = $("#book-edit-series-new-btn");
  const seriesIndexEl = $("#book-edit-series-index");

  const groupsStatusEl = $("#book-edit-groups-status");
  const groupsEl = $("#book-edit-groups");
  const groupsAddFormEl = $("#book-edit-groups-add");
  const groupsAddSelectEl = $("#book-edit-groups-add-select");
  const groupsAddBtnEl = $("#book-edit-groups-add-btn");
  const groupsAddStatusEl = $("#book-edit-groups-add-status");

  const shelvesStatusEl = $("#book-edit-shelves-status");
  const shelvesEl = $("#book-edit-shelves");

  const identifiersStatusEl = $("#book-edit-identifiers-status");
  const identifiersEl = $("#book-edit-identifiers");
  const fileInfoEl = $("#book-edit-file-info");

  if (
    !headerEl ||
    !headerTitleEl ||
    !headerAuthorsEl ||
    !headerSeriesEl ||
    !headerFileEl ||
    !headerCoverEl ||
    !rootEl ||
    !statusEl ||
    !errorEl ||
    !savedEl ||
    !saveStatusEl ||
    !formEl ||
    !saveBtn ||
    !titleEl ||
    !subtitleEl ||
    !summaryEl ||
    !publisherEl ||
    !languageEl ||
    !publishedDateEl ||
    !isbnEl ||
    !subjectsEl ||
    !authorsSelectedEl ||
    !authorsStatusEl ||
    !authorAddSelectEl ||
    !authorAddBtnEl ||
    !authorNewNameEl ||
    !authorNewBtnEl ||
    !seriesSelectEl ||
    !seriesStatusEl ||
    !seriesNewNameEl ||
    !seriesNewBtnEl ||
    !seriesIndexEl ||
    !groupsStatusEl ||
    !groupsEl ||
    !groupsAddFormEl ||
    !groupsAddSelectEl ||
    !groupsAddBtnEl ||
    !groupsAddStatusEl ||
    !shelvesStatusEl ||
    !shelvesEl ||
    !identifiersStatusEl ||
    !identifiersEl ||
    !fileInfoEl
  )
    return;

  function setStatus(text, isError) {
    setText(statusEl, text || "");
    statusEl.classList.toggle("error", !!isError);
  }

  function setError(text) {
    setText(errorEl, text || "");
    visible(errorEl, !!text);
  }

  function setSaved(on) {
    visible(savedEl, !!on);
  }

  function setSaving(on) {
    saveBtn.disabled = !!on;
    if (on) setText(saveStatusEl, "Saving…");
    else setText(saveStatusEl, "");
  }

  const bookId = rootEl.dataset ? rootEl.dataset.bookId : "";
  if (!bookId) {
    setStatus("Missing book id.", true);
    return;
  }

  const canManage = !!(me && me.capabilities && me.capabilities.can_manage_library);
  if (!canManage) {
    setStatus("Not allowed.", true);
    visible(rootEl, false);
    visible(headerEl, false);
    return;
  }

  const dom = {
    titleEl,
    subtitleEl,
    summaryEl,
    publisherEl,
    languageEl,
    publishedDateEl,
    isbnEl,
    subjectsEl,
    seriesIndexEl,
    seriesSelectEl,
  };

  let book = null;
  let identifiers = [];
  let allAuthors = [];
  let allSeries = [];
  let selectedAuthors = [];
  let allGroups = [];
  let groups = [];

  async function refreshShelves() {
    await refreshShelvesContext({
      bookId,
      fetchJSON,
      shelvesStatusEl,
      shelvesEl,
      setInlineStatus,
    });
  }

  async function refreshIdentifiers() {
    setInlineStatus(identifiersStatusEl, "Loading…", false);
    try {
      const list = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`);
      identifiers = Array.isArray(list) ? list : [];
      setInlineStatus(identifiersStatusEl, "", false);
      renderIdentifiersTable({ identifiers, identifiersEl });
    } catch (e) {
      console.error("Failed to load identifiers", e);
      setInlineStatus(identifiersStatusEl, "Failed to load.", true);
      setError(`Failed to load identifiers: ${extractApiErrorMessage(e)}`);
      identifiers = [];
      renderIdentifiersTable({ identifiers, identifiersEl });
    }
  }

  async function refreshBook() {
    book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    selectedAuthors = uniqueById(Array.isArray(book.authors) ? book.authors : []);
    groups = Array.isArray(book.groups) ? book.groups : [];

    applyBookToMetadataForm({ book, dom, selectedAuthors });

    renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });

    const titleText = book && book.title ? String(book.title) : "";
    const coverUrl = book && book.cover_url ? String(book.cover_url) : "";
    headerCoverEl.dataset.coverUrl = coverUrl;
    headerCoverEl.dataset.coverTitle = titleText;
    mountCovers(headerEl);
    renderFileInfo({ book, fileInfoEl });
    renderSelectedAuthors({ selectedAuthors, authorsSelectedEl });
    syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl });
    syncSeriesSelectOptions({ allSeries, seriesSelectEl, selectedId: book.series && book.series.id ? String(book.series.id) : "" });
    renderGroups({ groups, groupsEl });
    syncGroupsAddOptions({ allGroups, groups, groupsAddSelectEl, groupsAddBtnEl });
    await refreshShelves();
  }

  setStatus("Loading…", false);
  setError("");
  setSaved(false);
  visible(rootEl, false);
  visible(headerEl, false);

  try {
    await refreshBook();
    visible(headerEl, true);
    visible(rootEl, true);
    setStatus("", false);
  } catch (e) {
    console.error("Failed to load book for edit", { bookId, e });
    if (e && e.status === 404) setStatus("Book not found or not accessible.", true);
    else {
      setStatus("Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
    return;
  }

  // Load option lists.
  setInlineStatus(authorsStatusEl, "Loading…", false);
  try {
    allAuthors = uniqueById(await fetchAllPages("/api/v1/library/authors/"));
    setInlineStatus(authorsStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load authors", e);
    setInlineStatus(authorsStatusEl, "Failed to load.", true);
    allAuthors = [];
  }
  syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl });

  setInlineStatus(seriesStatusEl, "Loading…", false);
  try {
    allSeries = uniqueById(await fetchAllPages("/api/v1/library/series/"));
    setInlineStatus(seriesStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load series", e);
    setInlineStatus(seriesStatusEl, "Failed to load.", true);
    allSeries = [];
  }
  syncSeriesSelectOptions({ allSeries, seriesSelectEl, selectedId: book && book.series && book.series.id ? String(book.series.id) : "" });

  setInlineStatus(groupsStatusEl, "Loading…", false);
  try {
    allGroups = uniqueById(await fetchAllPages("/api/v1/library/groups/"));
    setInlineStatus(groupsStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load groups", e);
    setInlineStatus(groupsStatusEl, "Failed to load.", true);
    allGroups = [];
  }
  syncGroupsAddOptions({ allGroups, groups, groupsAddSelectEl, groupsAddBtnEl });

  await refreshIdentifiers();

  // Shelves interactions (remove book from shelf)
  shelvesEl.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.getAttribute("data-action") !== "remove-from-shelf") return;
    const shelfId = target.getAttribute("data-shelf-id");
    const itemId = target.getAttribute("data-item-id");
    if (!shelfId || !itemId) return;

    const ok = window.confirm("Remove this book from this shelf?");
    if (!ok) return;

    setInlineStatus(shelvesStatusEl, "Removing…", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;
      await fetchJSONWithOptions(
        `/api/v1/shelves/${encodeURIComponent(String(shelfId))}/items/${encodeURIComponent(String(itemId))}/`,
        { method: "DELETE", headers }
      );
      await refreshShelves();
      setInlineStatus(shelvesStatusEl, "", false);
    } catch (e2) {
      console.error("Failed to remove book from shelf", { shelfId, itemId, e2 });
      setInlineStatus(shelvesStatusEl, extractApiErrorMessage(e2) || "Failed to remove.", true);
    }
  });

  // Authors interactions
  authorsSelectedEl.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const id = t.getAttribute("data-remove-author-id");
    if (!id) return;
    selectedAuthors = selectedAuthors.filter((a) => String(a.id) !== String(id));
    renderSelectedAuthors({ selectedAuthors, authorsSelectedEl });
    syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl });
    if (book) book.authors = selectedAuthors;
    renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
  });

  authorAddBtnEl.addEventListener("click", () => {
    const id = authorAddSelectEl.value || "";
    if (!id) return;
    const found = allAuthors.find((a) => String(a.id) === String(id));
    if (!found) return;
    selectedAuthors.push(found);
    selectedAuthors = uniqueById(selectedAuthors);
    renderSelectedAuthors({ selectedAuthors, authorsSelectedEl });
    syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl });
    if (book) book.authors = selectedAuthors;
    renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
  });

  authorNewBtnEl.addEventListener("click", async () => {
    setError("");
    const name = (authorNewNameEl.value || "").trim();
    if (!name) {
      setError("Author name is required.");
      return;
    }
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(authorsStatusEl, "Creating…", false);
    try {
      const created = await fetchJSONWithOptions("/api/v1/library/authors/", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ name }),
      });
      allAuthors.push(created);
      allAuthors = uniqueById(allAuthors);
      selectedAuthors.push(created);
      selectedAuthors = uniqueById(selectedAuthors);
      authorNewNameEl.value = "";
      setInlineStatus(authorsStatusEl, "Created.", false);
      renderSelectedAuthors({ selectedAuthors, authorsSelectedEl });
      syncAuthorSelectOptions({ allAuthors, selectedAuthors, authorAddSelectEl, authorAddBtnEl });
      if (book) book.authors = selectedAuthors;
      renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
    } catch (e2) {
      console.error("Failed to create author", e2);
      setInlineStatus(authorsStatusEl, "Create failed.", true);
      setError(`Failed to create author: ${extractApiErrorMessage(e2)}`);
    }
  });

  // Series interactions
  seriesNewBtnEl.addEventListener("click", async () => {
    setError("");
    const name = (seriesNewNameEl.value || "").trim();
    if (!name) {
      setError("Series name is required.");
      return;
    }
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(seriesStatusEl, "Creating…", false);
    try {
      const created = await fetchJSONWithOptions("/api/v1/library/series/", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ name }),
      });
      allSeries.push(created);
      allSeries = uniqueById(allSeries);
      seriesNewNameEl.value = "";
      setInlineStatus(seriesStatusEl, "Created.", false);
      syncSeriesSelectOptions({ allSeries, seriesSelectEl, selectedId: created && created.id ? String(created.id) : "" });
      if (book) book.series = created;
      renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
    } catch (e2) {
      console.error("Failed to create series", e2);
      setInlineStatus(seriesStatusEl, "Create failed.", true);
      setError(`Failed to create series: ${extractApiErrorMessage(e2)}`);
    }
  });

  seriesSelectEl.addEventListener("change", () => {
    const sid = seriesSelectEl.value || "";
    if (book) book.series = sid ? allSeries.find((s) => String(s.id) === String(sid)) : null;
    renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
  });
  seriesIndexEl.addEventListener("input", () => {
    if (book) book.series_index = seriesIndexEl.value || null;
    renderHeader({ book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
  });

  // Groups interactions
  groupsEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const gid = t.getAttribute("data-group-remove-id");
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(groupsStatusEl, "Removing…", false);
    try {
      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
      );
      setInlineStatus(groupsStatusEl, "", false);
      await refreshBook();
    } catch (e) {
      console.error("Remove group assignment failed", e);
      setInlineStatus(groupsStatusEl, "Remove failed.", true);
      setError(`Failed to remove from group: ${extractApiErrorMessage(e)}`);
    }
  });

  groupsAddFormEl.addEventListener("submit", async (ev) => {
    ev.preventDefault();
    setError("");
    setInlineStatus(groupsAddStatusEl, "", false);
    const gid = (groupsAddSelectEl.value || "").trim();
    if (!gid) return;
    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }
    setInlineStatus(groupsAddStatusEl, "Adding…", false);
    try {
      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(gid))}/books/`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ book: String(bookId) }),
      });
      setInlineStatus(groupsAddStatusEl, "Added.", false);
      await refreshBook();
    } catch (e) {
      console.error("Add group assignment failed", e);
      setInlineStatus(groupsAddStatusEl, "Add failed.", true);
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    }
  });

  // Identifiers interactions (table event delegation)
  identifiersEl.addEventListener("click", async (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const action = t.getAttribute("data-ident-action");
    if (!action) return;

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    const row = t.closest ? t.closest("tr") : null;
    if (!row) return;
    const statusSpan = row.querySelector ? row.querySelector("[data-ident-status]") : null;
    const setRowStatus = (text, isError) => setInlineStatus(statusSpan, text, isError);

    if (action === "add") {
      const schemeEl = row.querySelector('[data-ident-add-field="scheme"]');
      const valueEl = row.querySelector('[data-ident-add-field="value"]');
      const sourceEl = row.querySelector('[data-ident-add-field="source"]');
      const primaryEl = row.querySelector('[data-ident-add-field="is_primary"]');
      const payload = {
        scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
        value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
        source: sourceEl && sourceEl.value != null ? String(sourceEl.value).trim() : "",
        is_primary: !!(primaryEl && primaryEl.checked),
      };
      setRowStatus("Adding…", false);
      try {
        await fetchJSONWithOptions(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/`, {
          method: "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
          body: JSON.stringify(payload),
        });
        setRowStatus("Added.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Add identifier failed", e);
        setRowStatus("Add failed.", true);
        const msg = extractApiErrorMessage(e);
        const body = e && e.body ? e.body : null;
        const fields = summarizeFieldErrors(body);
        setError(fields ? `${msg} (${fields})` : msg);
      }
      return;
    }

    const identId = row.getAttribute("data-ident-id") || "";
    if (!identId) return;

    if (action === "delete") {
      setRowStatus("Deleting…", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(String(identId))}/`,
          { method: "DELETE", headers: { Accept: "application/json", "X-CSRFToken": csrf } }
        );
        setRowStatus("Deleted.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Delete identifier failed", e);
        setRowStatus("Delete failed.", true);
        setError(`Failed to delete identifier: ${extractApiErrorMessage(e)}`);
      }
      return;
    }

    if (action === "save") {
      const schemeEl = row.querySelector('[data-ident-field="scheme"]');
      const valueEl = row.querySelector('[data-ident-field="value"]');
      const sourceEl = row.querySelector('[data-ident-field="source"]');
      const primaryEl = row.querySelector('[data-ident-field="is_primary"]');
      const payload = {
        scheme: schemeEl && schemeEl.value != null ? String(schemeEl.value).trim() : "",
        value: valueEl && valueEl.value != null ? String(valueEl.value).trim() : "",
        source: sourceEl && sourceEl.value != null ? String(sourceEl.value).trim() : "",
        is_primary: !!(primaryEl && primaryEl.checked),
      };
      setRowStatus("Saving…", false);
      try {
        await fetchJSONWithOptions(
          `/api/v1/library/books/${encodeURIComponent(String(bookId))}/identifiers/${encodeURIComponent(String(identId))}/`,
          {
            method: "PATCH",
            headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
            body: JSON.stringify(payload),
          }
        );
        setRowStatus("Saved.", false);
        await refreshIdentifiers();
      } catch (e) {
        console.error("Save identifier failed", e);
        setRowStatus("Save failed.", true);
        const msg = extractApiErrorMessage(e);
        const body = e && e.body ? e.body : null;
        const fields = summarizeFieldErrors(body);
        setError(fields ? `${msg} (${fields})` : msg);
      }
    }
  });

  async function saveBook() {
    setError("");
    setSaved(false);

    const built = buildBookPatchPayload({ dom: { ...dom, seriesSelectEl }, selectedAuthors });
    if (built && built.error) {
      setError(built.error);
      return;
    }
    const payload = built.payload;

    const csrf = getCsrfToken();
    if (!csrf) {
      setError("Missing CSRF token cookie. Reload the page and try again.");
      return;
    }

    setSaving(true);
    try {
      const updated = await fetchJSONWithOptions(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`, {
        method: "PATCH",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify(payload),
      });
      book = updated;
      setSaved(true);
      setText(saveStatusEl, "");
      await refreshBook();
      await refreshIdentifiers();
    } catch (e) {
      console.error("Failed to save book", { bookId, e });
      const msg = extractApiErrorMessage(e);
      const body = e && e.body ? e.body : null;
      const fields = summarizeFieldErrors(body);
      setError(fields ? `${msg} (${fields})` : msg);
    } finally {
      setSaving(false);
    }
  }

  formEl.addEventListener("submit", (ev) => {
    ev.preventDefault();
    saveBook().catch((e) => {
      console.error("saveBook failed", e);
      setError(extractApiErrorMessage(e));
    });
  });
}
