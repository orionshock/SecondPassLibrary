import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalErrorFromError, setText, visible } from "../layout.js";
import { setStatus as setInlineStatus } from "../ui/status.js";
import { fetchAllPages, uniqueById } from "./shared.js";
import { initTabs } from "../ui/tabs.js";
import { applyBookToMetadataForm, buildBookPatchPayload } from "./metadata.js";
import { renderSelectedAuthors, syncAuthorSelectOptions, syncSeriesSelectOptions } from "./authors_series.js";
import { renderGroups, syncGroupsAddOptions } from "./groups.js";
import { renderHeader, renderFileInfo } from "./identifiers_file.js";
import { refreshShelvesContext } from "./shelves.js";
import { bindAuthorSeriesActions } from "./author_series_actions.js";
import { bindGroupActions } from "./group_actions.js";
import { bindIdentifierActions, refreshIdentifiersContext } from "./identifiers_actions.js";
import { bindShelfActions } from "./shelf_actions.js";
import { mountCovers } from "../ui/covers.js";

export async function initBookEdit() {
  const me = await loadMeAndInitShell();
  initTabs(document, { defaultTab: "metadata" });

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

  function setError(text) {
    setText(errorEl, text || "");
    visible(errorEl, !!text);
  }

  function setSaved(on) {
    visible(savedEl, !!on);
  }

  function setSaving(on) {
    saveBtn.disabled = !!on;
    if (on) setText(saveStatusEl, "Saving...");
    else setText(saveStatusEl, "");
  }

  const bookId = rootEl.dataset ? rootEl.dataset.bookId : "";
  if (!bookId) {
    setInlineStatus(statusEl, "Missing book id.", true);
    return;
  }

  const canManage = !!(me && me.capabilities && me.capabilities.can_manage_library);
  if (!canManage) {
    setInlineStatus(statusEl, "Not allowed.", true);
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

  const state = {
    book: null,
    identifiers: [],
    allAuthors: [],
    allSeries: [],
    selectedAuthors: [],
    allGroups: [],
    groups: [],
  };

  async function refreshShelves() {
    await refreshShelvesContext({
      bookId,
      fetchJSON,
      shelvesStatusEl,
      shelvesEl,
      setInlineStatus,
    });
  }

  const refreshIdentifiers = () =>
    refreshIdentifiersContext({ bookId, identifiersStatusEl, identifiersEl, state, setError });

  async function refreshBook() {
    state.book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    state.selectedAuthors = uniqueById(Array.isArray(state.book.authors) ? state.book.authors : []);
    state.groups = Array.isArray(state.book.groups) ? state.book.groups : [];

    applyBookToMetadataForm({ book: state.book, dom, selectedAuthors: state.selectedAuthors });

    renderHeader({ book: state.book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });

    const titleText = state.book && state.book.title ? String(state.book.title) : "";
    const coverUrl = state.book && state.book.cover_url ? String(state.book.cover_url) : "";
    headerCoverEl.dataset.coverUrl = coverUrl;
    headerCoverEl.dataset.coverTitle = titleText;
    mountCovers(headerEl);
    renderFileInfo({ book: state.book, fileInfoEl });
    renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
    syncAuthorSelectOptions({ allAuthors: state.allAuthors, selectedAuthors: state.selectedAuthors, authorAddSelectEl, authorAddBtnEl });
    syncSeriesSelectOptions({ allSeries: state.allSeries, seriesSelectEl, selectedId: state.book.series && state.book.series.id ? String(state.book.series.id) : "" });
    renderGroups({ groups: state.groups, groupsEl });
    syncGroupsAddOptions({ allGroups: state.allGroups, groups: state.groups, groupsAddSelectEl, groupsAddBtnEl });
    await refreshShelves();
  }

  setInlineStatus(statusEl, "Loading...", false);
  setError("");
  setSaved(false);
  visible(rootEl, false);
  visible(headerEl, false);

  try {
    await refreshBook();
    visible(headerEl, true);
    visible(rootEl, true);
    setInlineStatus(statusEl, "", false);
  } catch (e) {
    console.error("Failed to load book for edit", { bookId, e });
    if (e && e.status === 404) setInlineStatus(statusEl, "Book not found or not accessible.", true);
    else {
      setInlineStatus(statusEl, "Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
    return;
  }

  // Load option lists.
  setInlineStatus(authorsStatusEl, "Loading...", false);
  try {
    state.allAuthors = uniqueById(await fetchAllPages("/api/v1/library/authors/"));
    setInlineStatus(authorsStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load authors", e);
    setInlineStatus(authorsStatusEl, "Failed to load.", true);
    state.allAuthors = [];
  }
  syncAuthorSelectOptions({ allAuthors: state.allAuthors, selectedAuthors: state.selectedAuthors, authorAddSelectEl, authorAddBtnEl });

  setInlineStatus(seriesStatusEl, "Loading...", false);
  try {
    state.allSeries = uniqueById(await fetchAllPages("/api/v1/library/series/"));
    setInlineStatus(seriesStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load series", e);
    setInlineStatus(seriesStatusEl, "Failed to load.", true);
    state.allSeries = [];
  }
  syncSeriesSelectOptions({ allSeries: state.allSeries, seriesSelectEl, selectedId: state.book && state.book.series && state.book.series.id ? String(state.book.series.id) : "" });

  setInlineStatus(groupsStatusEl, "Loading...", false);
  try {
    state.allGroups = uniqueById(await fetchAllPages("/api/v1/library/groups/"));
    setInlineStatus(groupsStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load groups", e);
    setInlineStatus(groupsStatusEl, "Failed to load.", true);
    state.allGroups = [];
  }
  syncGroupsAddOptions({ allGroups: state.allGroups, groups: state.groups, groupsAddSelectEl, groupsAddBtnEl });

  await refreshIdentifiers();

  bindShelfActions({ shelvesEl, shelvesStatusEl, refreshShelves });
  bindAuthorSeriesActions({
    state,
    authorsSelectedEl,
    authorsStatusEl,
    authorAddSelectEl,
    authorAddBtnEl,
    authorNewNameEl,
    authorNewBtnEl,
    seriesSelectEl,
    seriesStatusEl,
    seriesNewNameEl,
    seriesNewBtnEl,
    seriesIndexEl,
    headerTitleEl,
    headerAuthorsEl,
    headerSeriesEl,
    headerFileEl,
    setError,
  });
  bindGroupActions({
    bookId,
    groupsEl,
    groupsStatusEl,
    groupsAddFormEl,
    groupsAddSelectEl,
    groupsAddStatusEl,
    refreshBook,
    setError,
  });
  bindIdentifierActions({ bookId, identifiersEl, refreshIdentifiers, setError });

  async function saveBook() {
    setError("");
    setSaved(false);

    const built = buildBookPatchPayload({ dom: { ...dom, seriesSelectEl }, selectedAuthors: state.selectedAuthors });
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
      state.book = updated;
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
