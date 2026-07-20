import {
  fetchAllPaginatedResults,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
  summarizeFieldErrors,
} from "../api.js";
import { canManageLibrary } from "../auth.js";
import {
  $,
  advancedLibraryGroupsEnabled,
  loadMeAndInitShell,
  setText,
  visible,
} from "../layout.js";
import { setStatus } from "../ui/status.js";
import { uniqueById } from "./shared.js";
import { initBookEditNavigation } from "./navigation.js";
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
import { setBreadcrumbs } from "../ui/breadcrumbs.js";
import { bindCatalogTagActions, renderCatalogTags } from "./catalog_tags.js";
import { initBookCoverEditor } from "../library/cover_editor.js";

function bookDisplayTitle(book) {
  return book && book.title ? String(book.title) : "Untitled book";
}

function safeBookEditError(error, fallback) {
  const body = error && error.body && typeof error.body === "object" ? error.body : null;
  const fields = summarizeFieldErrors(body);
  if (fields) return `${fallback} (${fields})`;
  if (body && body.detail) return String(body.detail).slice(0, 240);
  return fallback;
}

function syncBookEditBreadcrumbs({ bookId, title }) {
  setBreadcrumbs([
    { label: "Library", href: "/library/" },
    { label: "Books", href: "/library/?view=books" },
    { label: title || "Book", href: `/library/books/${encodeURIComponent(String(bookId))}/` },
    { label: "Edit", current: true },
  ]);
}

export async function initBookEdit() {
  const me = await loadMeAndInitShell();
  const headerEl = $("#book-edit-header");
  const headerTitleEl = $("#book-edit-header-title");
  const headerAuthorsEl = $("#book-edit-header-authors");
  const headerSeriesEl = $("#book-edit-header-series");
  const headerDownloadEl = $("#book-edit-cover-download");
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
  const descriptionEl = $("#book-edit-description");
  const publisherEl = $("#book-edit-publisher");
  const languageEl = $("#book-edit-language");
  const publishedDateEl = $("#book-edit-published-date");
  const catalogTagsEl = $("#book-edit-catalog-tags");
  const catalogTagsStatusEl = $("#book-edit-catalog-tags-status");
  const catalogTagInputEl = $("#book-edit-catalog-tag-input");
  const catalogTagOptionsEl = $("#book-edit-catalog-tag-options");
  const catalogTagAddEl = $("#book-edit-catalog-tag-add");

  const authorsSelectedEl = $("#book-edit-authors-selected");
  const authorsStatusEl = $("#book-edit-authors-status");
  const authorAddSelectEl = $("#book-edit-author-add-select");
  const authorAddBtnEl = $("#book-edit-author-add-btn");

  const seriesSelectEl = $("#book-edit-series-select");
  const seriesStatusEl = $("#book-edit-series-status");
  const seriesIndexEl = $("#book-edit-series-index");

  const groupsStatusEl = $("#book-edit-groups-status");
  const groupsEl = $("#book-edit-groups");
  const groupsAddFormEl = $("#book-edit-groups-add");
  const groupsAddSelectEl = $("#book-edit-groups-add-select");
  const groupsAddBtnEl = $("#book-edit-groups-add-btn");
  const groupsAddStatusEl = $("#book-edit-groups-add-status");
  const groupsFeatureEnabled =
    advancedLibraryGroupsEnabled() &&
    !!groupsStatusEl &&
    !!groupsEl &&
    !!groupsAddFormEl &&
    !!groupsAddSelectEl &&
    !!groupsAddBtnEl &&
    !!groupsAddStatusEl;

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
    !headerDownloadEl ||
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
    !descriptionEl ||
    !publisherEl ||
    !languageEl ||
    !publishedDateEl ||
    !catalogTagsEl ||
    !catalogTagsStatusEl ||
    !catalogTagInputEl ||
    !catalogTagOptionsEl ||
    !catalogTagAddEl ||
    !authorsSelectedEl ||
    !authorsStatusEl ||
    !authorAddSelectEl ||
    !authorAddBtnEl ||
    !seriesSelectEl ||
    !seriesStatusEl ||
    !seriesIndexEl ||
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
    setStatus(statusEl, "Missing book id.", true);
    return;
  }
  initBookEditNavigation(rootEl);
  syncBookEditBreadcrumbs({ bookId, title: "Book" });

  const canManage = canManageLibrary(me);
  if (!canManage) {
    setStatus(statusEl, "Not allowed.", true);
    visible(rootEl, false);
    visible(headerEl, false);
    return;
  }

  const dom = {
    titleEl,
    subtitleEl,
    descriptionEl,
    publisherEl,
    languageEl,
    publishedDateEl,
    seriesIndexEl,
    seriesSelectEl,
  };

  const state = {
    book: null,
    identifiers: [],
    allAuthors: [],
    allSeries: [],
    selectedAuthors: [],
    catalogTags: [],
    allCatalogTags: [],
    allGroups: [],
    groups: [],
  };

  function renderHeaderCover(url, title) {
    headerCoverEl.dataset.coverUrl = String(url || "");
    headerCoverEl.dataset.coverTitle = String(title || "");
    headerCoverEl.dataset.coverMounted = "0";
    mountCovers(headerEl);
  }

  const coverEditor = initBookCoverEditor({
    bookId,
    onCoverChanged(url, book) {
      state.book = { ...(state.book || {}), ...(book || {}), cover_url: url };
      renderHeaderCover(url, bookDisplayTitle(state.book));
    },
  });

  async function refreshShelves() {
    await refreshShelvesContext({
      bookId,
      fetchJSON,
      shelvesStatusEl,
      shelvesEl,
    });
  }

  const refreshIdentifiers = () =>
    refreshIdentifiersContext({ identifiersStatusEl, identifiersEl, state });

  async function refreshBook() {
    state.book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);
    state.selectedAuthors = uniqueById(Array.isArray(state.book.authors) ? state.book.authors : []);
    state.identifiers = Array.isArray(state.book.identifiers) ? state.book.identifiers.slice() : [];
    state.catalogTags = Array.isArray(state.book.catalog_tags) ? state.book.catalog_tags.slice() : [];
    state.groups =
      groupsFeatureEnabled && Array.isArray(state.book.groups) ? state.book.groups : [];

    applyBookToMetadataForm({ book: state.book, dom, selectedAuthors: state.selectedAuthors });

    renderHeader({ book: state.book, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
    syncBookEditBreadcrumbs({ bookId, title: bookDisplayTitle(state.book) });

    const titleText = state.book && state.book.title ? String(state.book.title) : "";
    const coverUrl = state.book && state.book.cover_url ? String(state.book.cover_url) : "";
    renderHeaderCover(coverUrl, titleText);
    if (coverEditor) coverEditor.setCurrentCover({ url: coverUrl, title: titleText });
    renderFileInfo({ book: state.book, fileInfoEl });
    renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
    renderCatalogTags({ state, selectedEl: catalogTagsEl, optionsEl: catalogTagOptionsEl });
    syncAuthorSelectOptions({ allAuthors: state.allAuthors, selectedAuthors: state.selectedAuthors, authorAddSelectEl, authorAddBtnEl });
    syncSeriesSelectOptions({ allSeries: state.allSeries, seriesSelectEl, selectedId: state.book.series && state.book.series.id ? String(state.book.series.id) : "" });
    if (groupsFeatureEnabled) {
      renderGroups({ groups: state.groups, groupsEl });
      syncGroupsAddOptions({ allGroups: state.allGroups, groups: state.groups, groupsAddSelectEl, groupsAddBtnEl });
    }
    await refreshShelves();
  }

  setStatus(statusEl, "Loading...", false);
  setError("");
  setSaved(false);
  visible(rootEl, false);
  visible(headerEl, false);

  try {
    await refreshBook();
    visible(headerEl, true);
    visible(rootEl, true);
    setStatus(statusEl, "", false);
  } catch (e) {
    console.error("Failed to load book for edit", { bookId, e });
    if (e && e.status === 404) setStatus(statusEl, "Book not found or not accessible.", true);
    else {
      setStatus(statusEl, "Error loading book.", true);
      setError(safeBookEditError(e, "Failed to load book."));
    }
    return;
  }

  // Load option lists.
  setStatus(authorsStatusEl, "Loading...", false);
  try {
    state.allAuthors = uniqueById(await fetchAllPaginatedResults("/api/v1/library/authors/"));
    const authorsById = new Map(state.allAuthors.map((author) => [String(author.id), author]));
    state.selectedAuthors = state.selectedAuthors.map((author) => ({
      ...author,
      ...(authorsById.get(String(author.id)) || {}),
    }));
    renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
    setStatus(authorsStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load authors", e);
    setStatus(authorsStatusEl, "Failed to load.", true);
    state.allAuthors = [];
  }
  syncAuthorSelectOptions({ allAuthors: state.allAuthors, selectedAuthors: state.selectedAuthors, authorAddSelectEl, authorAddBtnEl });

  setStatus(seriesStatusEl, "Loading...", false);
  try {
    state.allSeries = uniqueById(await fetchAllPaginatedResults("/api/v1/library/series/"));
    setStatus(seriesStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load series", e);
    setStatus(seriesStatusEl, "Failed to load.", true);
    state.allSeries = [];
  }
  syncSeriesSelectOptions({ allSeries: state.allSeries, seriesSelectEl, selectedId: state.book && state.book.series && state.book.series.id ? String(state.book.series.id) : "" });

  setStatus(catalogTagsStatusEl, "Loading...", false);
  try {
    state.allCatalogTags = uniqueById(await fetchAllPaginatedResults("/api/v1/library/tags/"));
    setStatus(catalogTagsStatusEl, "", false);
  } catch (e) {
    console.error("Failed to load Catalog Tags", e);
    state.allCatalogTags = [];
    setStatus(catalogTagsStatusEl, "Failed to load Catalog Tags.", true);
  }
  renderCatalogTags({ state, selectedEl: catalogTagsEl, optionsEl: catalogTagOptionsEl });

  if (groupsFeatureEnabled) {
    setStatus(groupsStatusEl, "Loading...", false);
    try {
      state.allGroups = uniqueById(await fetchAllPaginatedResults("/api/v1/library/groups/"));
      setStatus(groupsStatusEl, "", false);
    } catch (e) {
      console.error("Failed to load groups", e);
      setStatus(groupsStatusEl, "Failed to load.", true);
      state.allGroups = [];
    }
    syncGroupsAddOptions({ allGroups: state.allGroups, groups: state.groups, groupsAddSelectEl, groupsAddBtnEl });
  }

  refreshIdentifiers();

  bindShelfActions({ shelvesEl, shelvesStatusEl, refreshShelves });
  bindAuthorSeriesActions({
    state,
    authorsSelectedEl,
    authorAddSelectEl,
    authorAddBtnEl,
    seriesSelectEl,
    seriesIndexEl,
    headerTitleEl,
    headerAuthorsEl,
    headerSeriesEl,
  });
  if (groupsFeatureEnabled) {
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
  }
  bindIdentifierActions({
    identifiersEl,
    refreshIdentifiers,
    state,
    setError,
    markDirty: () => setSaved(false),
  });
  bindCatalogTagActions({
    state,
    selectedEl: catalogTagsEl,
    inputEl: catalogTagInputEl,
    addBtnEl: catalogTagAddEl,
    rerender: () => renderCatalogTags({ state, selectedEl: catalogTagsEl, optionsEl: catalogTagOptionsEl }),
    markDirty: () => setSaved(false),
  });

  async function saveBook() {
    setError("");
    setSaved(false);

    const built = buildBookPatchPayload({
      dom: { ...dom, seriesSelectEl },
      selectedAuthors: state.selectedAuthors,
      identifiers: state.identifiers,
      catalogTags: state.catalogTags,
    });
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
      if (updated.series && updated.series.id) {
        state.allSeries = uniqueById([...state.allSeries, updated.series]);
      }
      setSaved(true);
      setText(saveStatusEl, "");
      await refreshBook();
      refreshIdentifiers();
    } catch (e) {
      setError(safeBookEditError(e, "Failed to save book."));
    } finally {
      setSaving(false);
    }
  }

  formEl.addEventListener("submit", (ev) => {
    ev.preventDefault();
    saveBook().catch((e) => {
      setError(safeBookEditError(e, "Failed to save book."));
    });
  });
}
