import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { escapeHtml, setGlobalError, visible } from "../layout.js";
import { isLibrarian, isManagerOrOwner, pagedListController, renderBooksCompact, setStatus, truthy } from "./shared.js";
import { mountCovers } from "../ui/covers.js";

export async function initGroupBooksTab({
  me,
  groupId,
  allowBookManage,
  bookSearchForm,
  bookSearchInput,
  bookSearchStatus,
  bookSearchWrap,
  bookSearchResults,
  bookSearchPrev,
  bookSearchNext,
  uuidDebugDetails,
  addBookForm,
  addBookInput,
  addBookStatus,
  booksStatus,
  booksResults,
  booksNext,
  booksPrev,
}) {
  visible(bookSearchForm, allowBookManage);
  visible(bookSearchWrap, false);
  // Keep the manual UUID add path as a collapsed debug-only fallback.
  visible(uuidDebugDetails, allowBookManage && (isManagerOrOwner(me) || isLibrarian(me)));
  visible(addBookForm, false);

  const booksCtl = await pagedListController({
    statusEl: booksStatus,
    resultsEl: booksResults,
    nextBtn: booksNext,
    prevBtn: booksPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`,
    emptyText: "No books in this group.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: allowBookManage }),
  });

  if (!allowBookManage) return { booksCtl };

  function setAddBookStatus(text, isError) {
    setStatus(addBookStatus, text, isError);
  }
  function setBookSearchStatus(text, isError) {
    setStatus(bookSearchStatus, text, isError);
  }

  const groupBookIds = new Set();

  async function loadGroupBookIds() {
    groupBookIds.clear();
    let url = `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/?page_size=200`;
    for (let i = 0; i < 20 && url; i++) {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      for (const b of results) {
        if (b && b.id) groupBookIds.add(String(b.id));
      }
      url = payload.next || null;
    }
  }

  try {
    await loadGroupBookIds();
  } catch (e) {
    console.error("Failed to pre-load group book ids", { groupId, e });
  }

  function renderBookSearchResults(payload) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (!results.length) return "";

    return results
      .map((b) => {
        const id = b && b.id ? String(b.id) : "";
        const inGroup = id && groupBookIds.has(id);

        const title = b.title || "(Untitled)";
        const coverUrl = b.cover_url ? String(b.cover_url) : "";
        const subtitle = b.subtitle ? ` <span class="muted">â€” ${escapeHtml(b.subtitle)}</span>` : "";
        const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
        const series = b.series && b.series.name ? b.series.name : "";
        const seriesIndex = b.series_index != null && b.series_index !== "" ? String(b.series_index) : "";

        const fileBadge = b.file ? '<span class="pill">File</span>' : "";
        const inGroupBadge = inGroup ? '<span class="pill">Already in group</span>' : "";
        const badges = [fileBadge, inGroupBadge].filter(truthy).join(" ");

        const metaBits = [];
        if (authors.length) metaBits.push(escapeHtml(authors.join(", ")));
        if (series) metaBits.push(`${escapeHtml(series)}${seriesIndex ? ` #${escapeHtml(seriesIndex)}` : ""}`);
        const meta = metaBits.length ? `<div class="muted">${metaBits.join(" Â· ")}</div>` : "";

        const addBtn =
          !inGroup && id
            ? `<button class="button" type="button" data-action="add-book" data-book-id="${escapeHtml(
                id
              )}">Add</button>`
            : "";

        return `
            <article class="book book--with-cover">
              <div class="book__cover" data-cover-url="${escapeHtml(coverUrl)}" data-cover-title="${escapeHtml(title)}"></div>
              <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
                <div>
                  <h3 class="book__title" style="display:inline;">${escapeHtml(title)}${subtitle}</h3>
                  ${badges ? ` <span style="margin-left: 8px;">${badges}</span>` : ""}
                  ${meta}
                </div>
                ${addBtn ? `<div>${addBtn}</div>` : ""}
              </div>
            </article>
          `.trim();
      })
      .join("");
  }

  let searchNextUrl = null;
  let searchPrevUrl = null;
  let lastSearchUrl = null;

  async function loadBookSearch(url) {
    setBookSearchStatus("Searchingâ€¦", false);
    bookSearchResults.innerHTML = "";
    bookSearchNext.disabled = true;
    bookSearchPrev.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (!results.length) {
        setBookSearchStatus("No results.", false);
        searchNextUrl = null;
        searchPrevUrl = null;
        visible(bookSearchWrap, true);
        lastSearchUrl = url;
        return;
      }

      setBookSearchStatus(
        payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "",
        false
      );
      bookSearchResults.innerHTML = renderBookSearchResults(payload);
      mountCovers(bookSearchResults);
      searchNextUrl = payload.next || null;
      searchPrevUrl = payload.previous || null;
      bookSearchNext.disabled = !searchNextUrl;
      bookSearchPrev.disabled = !searchPrevUrl;
      visible(bookSearchWrap, true);
      lastSearchUrl = url;
    } catch (e) {
      console.error("Failed to search books", { groupId, url, e });
      if (e && e.status === 403) setBookSearchStatus("Permission denied.", true);
      else setBookSearchStatus("Search failed.", true);
      setGlobalError(extractApiErrorMessage(e));
      searchNextUrl = null;
      searchPrevUrl = null;
      visible(bookSearchWrap, true);
      lastSearchUrl = url;
    }
  }

  bookSearchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const term = (bookSearchInput.value || "").trim();
    if (!term) {
      setBookSearchStatus("Enter a search term.", true);
      visible(bookSearchWrap, false);
      return;
    }
    const url = `/api/v1/library/books/?q=${encodeURIComponent(term)}`;
    await loadBookSearch(url);
  });

  bookSearchNext.addEventListener("click", async () => {
    if (searchNextUrl) await loadBookSearch(searchNextUrl);
  });
  bookSearchPrev.addEventListener("click", async () => {
    if (searchPrevUrl) await loadBookSearch(searchPrevUrl);
  });

  bookSearchResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.getAttribute("data-action") !== "add-book") return;
    const bookId = target.getAttribute("data-book-id");
    if (!bookId) return;

    setBookSearchStatus("Addingâ€¦", false);
    setGlobalError("");

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ book: bookId }),
      });

      groupBookIds.add(String(bookId));
      setBookSearchStatus("Added.", false);
      await booksCtl.reloadFirstPage();

      try {
        await loadGroupBookIds();
      } catch (e2) {
        console.error("Failed to refresh group book ids", e2);
      }

      if (lastSearchUrl) await loadBookSearch(lastSearchUrl);
    } catch (e2) {
      console.error("Failed to add book to group", { groupId, bookId, e2 });
      setBookSearchStatus(extractApiErrorMessage(e2), true);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  addBookForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    setAddBookStatus("Addingâ€¦", false);
    setGlobalError("");

    const bookId = (addBookInput.value || "").trim();
    if (!bookId) {
      setAddBookStatus("Enter a book UUID.", true);
      return;
    }

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ book: bookId }),
      });

      setAddBookStatus("Added.", false);
      addBookInput.value = "";
      await booksCtl.reloadFirstPage();
    } catch (e2) {
      console.error("Failed to add book to group", { groupId, bookId, e2 });
      setAddBookStatus(extractApiErrorMessage(e2), true);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  booksResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.getAttribute("data-action") !== "remove-book") return;
    const bookId = target.getAttribute("data-book-id");
    if (!bookId) return;

    setGlobalError("");
    setStatus(booksStatus, "Removingâ€¦", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers }
      );
      await booksCtl.reloadFirstPage();
    } catch (e2) {
      console.error("Failed to remove book from group", { groupId, bookId, e2 });
      setStatus(booksStatus, extractApiErrorMessage(e2), true);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });

  return { booksCtl };
}
