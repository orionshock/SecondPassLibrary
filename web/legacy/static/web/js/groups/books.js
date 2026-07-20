import { fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";
import { groupMutationErrorMessage, renderBooksCompact } from "./shared.js";
import {
  groupBooksApiUrl,
} from "./book_pagination.js";
import { createGroupEditPager, syncGroupEditPageUrl } from "./edit_pagination.js";

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
  bookSearchInput.value = new URLSearchParams(window.location.search).get("q") || "";

  const booksCtl = await createGroupEditPager({
    key: "books",
    tab: "books",
    statusEl: booksStatus,
    resultsEl: booksResults,
    nextBtn: booksNext,
    prevBtn: booksPrev,
    initialUrl: (search) => groupBooksApiUrl(groupId, search),
    emptyText: "No books in this group.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: allowBookManage }),
    onLoaded: (_payload, _results, context) => {
      if (context.reason === "remove-back") {
        syncGroupEditPageUrl("books", context.url, { replace: true });
      }
    },
    loadErrorText: "Unable to load assigned books.",
  });

  if (!allowBookManage) return { booksCtl };

  function setBookSearchStatus(text, isError) {
    setStatus(bookSearchStatus, text, isError);
  }

  const bookSearchCtl = await createGroupEditPager({
    key: "book-search",
    tab: "add-books",
    statusEl: bookSearchStatus,
    resultsEl: bookSearchResults,
    nextBtn: bookSearchNext,
    prevBtn: bookSearchPrev,
    initialUrl: (search) => {
      const query = new URLSearchParams(search || "").get("q") || "";
      const params = new URLSearchParams({
        q: query,
        ordering: "title",
        exclude_group: String(groupId),
      });
      return `/api/v1/library/search?${params.toString()}`;
    },
    emptyText: "No results.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: false, canAdd: true }),
    onLoaded: () => visible(bookSearchWrap, true),
    loadErrorText: "Book search failed.",
    autoLoad: !!new URLSearchParams(window.location.search).get("q"),
  });

  bookSearchForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const term = (bookSearchInput.value || "").trim();
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
