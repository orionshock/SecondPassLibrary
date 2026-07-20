import { fetchJSONWithOptions, getCsrfToken, summarizeFieldErrors } from "../api.js";
import { setStatus } from "../ui/status.js";
import { renderHeader } from "./identifiers_file.js";
import { renderSelectedAuthors, syncAuthorSelectOptions, syncSeriesSelectOptions } from "./authors_series.js";
import { uniqueById } from "./shared.js";

function rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl }) {
  renderHeader({
    book: state.book,
    headerTitleEl,
    headerAuthorsEl,
    headerSeriesEl,
    headerDownloadEl,
  });
}

export function bindAuthorSeriesActions({
  state,
  authorsSelectedEl,
  authorAddSelectEl,
  authorAddBtnEl,
  authorCreateFormEl,
  authorNewEl,
  authorCreateBtnEl,
  authorCreateStatusEl,
  seriesSelectEl,
  seriesNewEl,
  seriesIndexEl,
  headerTitleEl,
  headerAuthorsEl,
  headerSeriesEl,
  headerDownloadEl,
}) {
  authorsSelectedEl.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!t || !t.getAttribute) return;
    const id = t.getAttribute("data-remove-author-id");
    if (!id) return;
    state.selectedAuthors = state.selectedAuthors.filter((a) => String(a.id) !== String(id));
    renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
    syncAuthorSelectOptions({
      allAuthors: state.allAuthors,
      selectedAuthors: state.selectedAuthors,
      authorAddSelectEl,
      authorAddBtnEl,
    });
    if (state.book) state.book.authors = state.selectedAuthors;
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
  });

  authorAddBtnEl.addEventListener("click", () => {
    const id = authorAddSelectEl.value || "";
    if (!id) return;
    const found = state.allAuthors.find((a) => String(a.id) === String(id));
    if (!found) return;
    state.selectedAuthors.push(found);
    state.selectedAuthors = uniqueById(state.selectedAuthors);
    renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
    syncAuthorSelectOptions({
      allAuthors: state.allAuthors,
      selectedAuthors: state.selectedAuthors,
      authorAddSelectEl,
      authorAddBtnEl,
    });
    if (state.book) state.book.authors = state.selectedAuthors;
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
  });

  authorCreateFormEl.addEventListener("submit", async (event) => {
    event.preventDefault();
    const name = String(authorNewEl.value || "").trim();
    if (!name) {
      setStatus(authorCreateStatusEl, "Enter an author name.", true);
      return;
    }
    const csrf = getCsrfToken();
    authorNewEl.disabled = true;
    authorCreateBtnEl.disabled = true;
    setStatus(authorCreateStatusEl, "Creating...", false);
    try {
      const author = await fetchJSONWithOptions("/api/v1/library/authors/", {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
          ...(csrf ? { "X-CSRFToken": csrf } : {}),
        },
        body: JSON.stringify({ name }),
      });
      state.allAuthors = uniqueById([...state.allAuthors, author]);
      state.selectedAuthors = uniqueById([...state.selectedAuthors, author]);
      if (state.book) state.book.authors = state.selectedAuthors;
      renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
      syncAuthorSelectOptions({
        allAuthors: state.allAuthors,
        selectedAuthors: state.selectedAuthors,
        authorAddSelectEl,
        authorAddBtnEl,
      });
      rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
      authorNewEl.value = "";
      setStatus(authorCreateStatusEl, "Author created and selected. Save to apply.", false);
    } catch (error) {
      const fields = summarizeFieldErrors(error && error.body);
      setStatus(authorCreateStatusEl, fields || "Author could not be created.", true);
    } finally {
      authorNewEl.disabled = false;
      authorCreateBtnEl.disabled = false;
    }
  });

  seriesSelectEl.addEventListener("change", () => {
    if (seriesSelectEl.value) seriesNewEl.value = "";
    const sid = seriesSelectEl.value || "";
    if (state.book) {
      state.book.series = sid ? state.allSeries.find((s) => String(s.id) === String(sid)) : null;
    }
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
  });
  seriesNewEl.addEventListener("input", () => {
    const name = (seriesNewEl.value || "").trim();
    if (name) seriesSelectEl.value = "";
    if (state.book) {
      state.book.series = name ? { name, series_index: seriesIndexEl.value || null } : null;
    }
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
  });
  seriesIndexEl.addEventListener("input", () => {
    if (state.book && state.book.series) {
      state.book.series.series_index = seriesIndexEl.value || null;
    }
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerDownloadEl });
  });
}
