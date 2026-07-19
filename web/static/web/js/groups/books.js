import { fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { escapeHtml, setGlobalError, visible } from "../layout.js";
import { createPagedListController } from "../ui/paged_list.js";
import { setStatus } from "../ui/status.js";
import { groupMutationErrorMessage, renderBooksCompact } from "./shared.js";
import {
  groupBookPageStatus,
  groupBooksApiUrl,
  syncGroupBookPage,
} from "./book_pagination.js";

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
  booksStatus,
  booksResults,
  booksNext,
  booksPrev,
}) {
  visible(bookSearchForm, allowBookManage);
  visible(bookSearchWrap, false);

  const booksCtl = await createPagedListController({
    statusEl: booksStatus,
    resultsEl: booksResults,
    nextBtn: booksNext,
    prevBtn: booksPrev,
    initialUrl: groupBooksApiUrl(groupId),
    emptyText: "No books in this group.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: allowBookManage }),
    formatStatus: (payload, results, context) =>
      groupBookPageStatus(payload, results, context.url),
    onLoaded: (_payload, _results, context) => {
      if (context.reason === "next" || context.reason === "previous") {
        syncGroupBookPage(context.url);
      } else if (context.reason === "remove-back") {
        syncGroupBookPage(context.url, { replace: true });
      }
    },
    loadErrorText: "Unable to load assigned books.",
  });

  window.addEventListener("popstate", async () => {
    await booksCtl.load(groupBooksApiUrl(groupId), { reason: "history" });
  });

  if (!allowBookManage) return { booksCtl };

  function setBookSearchStatus(text, isError) {
    setStatus(bookSearchStatus, text, isError);
  }

  function renderBookSearchResults(payload) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (!results.length) return "";

    return results
      .map((b) => {
        const id = b && b.id ? String(b.id) : "";
        const title = b.title || "(Untitled)";
        const coverUrl = b.cover_url ? String(b.cover_url) : "";
        const subtitle = b.subtitle ? ` <span class="muted">- ${escapeHtml(b.subtitle)}</span>` : "";
        const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
        const series = b.series && b.series.name ? b.series.name : "";
        const seriesIndex =
          b.series && b.series.series_index != null && b.series.series_index !== ""
            ? String(b.series.series_index)
            : "";

        const metaBits = [];
        if (authors.length) metaBits.push(escapeHtml(authors.join(", ")));
        if (series) metaBits.push(`${escapeHtml(series)}${seriesIndex ? ` #${escapeHtml(seriesIndex)}` : ""}`);
        const meta = metaBits.length ? `<div class="muted">${metaBits.join("  -  ")}</div>` : "";

        const addBtn =
          id
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
                  ${meta}
                </div>
                ${addBtn ? `<div>${addBtn}</div>` : ""}
              </div>
            </article>
          `.trim();
      })
      .join("");
  }

  const bookSearchCtl = await createPagedListController({
    statusEl: bookSearchStatus,
    resultsEl: bookSearchResults,
    nextBtn: bookSearchNext,
    prevBtn: bookSearchPrev,
    initialUrl: "/api/v1/library/books/",
    emptyText: "No results.",
    render: (payload) => renderBookSearchResults(payload),
    onLoaded: () => visible(bookSearchWrap, true),
    loadErrorText: "Book search failed.",
    autoLoad: false,
  });

  bookSearchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const term = (bookSearchInput.value || "").trim();
    if (!term) {
      setBookSearchStatus("Enter a search term.", true);
      visible(bookSearchWrap, false);
      return;
    }
    const params = new URLSearchParams({
      q: term,
      ordering: "title",
      exclude_group: String(groupId),
    });
    const url = `/api/v1/library/search?${params.toString()}`;
    visible(bookSearchWrap, true);
    await bookSearchCtl.load(url, { reason: "search" });
  });

  bookSearchResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.getAttribute("data-action") !== "add-book") return;
    const bookId = target.getAttribute("data-book-id");
    if (!bookId) return;

    setBookSearchStatus("Adding...", false);
    setGlobalError("");

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json", "Content-Type": "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`, {
        method: "POST",
        headers,
        body: JSON.stringify({ book_id: bookId }),
      });

      setBookSearchStatus("Added.", false);
      await booksCtl.reload();

      await bookSearchCtl.reload();
    } catch (e2) {
      console.error("Failed to add book to group", { groupId, bookId, e2 });
      const message = groupMutationErrorMessage(e2, "Failed to add book to group.");
      setBookSearchStatus(message, true);
      setGlobalError(message);
    }
  });

  booksResults.addEventListener("click", async (e) => {
    const target = e.target;
    if (!target || target.nodeType !== 1) return;
    if (target.getAttribute("data-action") !== "remove-book") return;
    const bookId = target.getAttribute("data-book-id");
    if (!bookId) return;

    setGlobalError("");
    setStatus(booksStatus, "Removing...", false);
    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      await fetchJSONWithOptions(
        `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/${encodeURIComponent(String(bookId))}/`,
        { method: "DELETE", headers }
      );
      const state = booksCtl.getState();
      if (state.resultCount === 1 && state.previousUrl) {
        await booksCtl.loadPrevious("remove-back");
      } else {
        await booksCtl.reload();
      }
    } catch (e2) {
      console.error("Failed to remove book from group", { groupId, bookId, e2 });
      const message = groupMutationErrorMessage(e2, "Failed to remove book from group.");
      setStatus(booksStatus, message, true);
      setGlobalError(message);
    }
  });

  return { booksCtl };
}
