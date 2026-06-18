import { extractApiErrorMessage, fetchJSONWithOptions, getCsrfToken } from "../api.js";
import { renderHeader } from "./identifiers_file.js";
import { renderSelectedAuthors, syncAuthorSelectOptions, syncSeriesSelectOptions } from "./authors_series.js";
import { setStatus } from "../ui/status.js";
import { uniqueById } from "./shared.js";

function rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl }) {
  renderHeader({
    book: state.book,
    headerTitleEl,
    headerAuthorsEl,
    headerSeriesEl,
    headerFileEl,
  });
}

export function bindAuthorSeriesActions({
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
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
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
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
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
    setStatus(authorsStatusEl, "Creating...", false);
    try {
      const created = await fetchJSONWithOptions("/api/v1/library/authors/", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ name }),
      });
      state.allAuthors.push(created);
      state.allAuthors = uniqueById(state.allAuthors);
      state.selectedAuthors.push(created);
      state.selectedAuthors = uniqueById(state.selectedAuthors);
      authorNewNameEl.value = "";
      setStatus(authorsStatusEl, "Created.", false);
      renderSelectedAuthors({ selectedAuthors: state.selectedAuthors, authorsSelectedEl });
      syncAuthorSelectOptions({
        allAuthors: state.allAuthors,
        selectedAuthors: state.selectedAuthors,
        authorAddSelectEl,
        authorAddBtnEl,
      });
      if (state.book) state.book.authors = state.selectedAuthors;
      rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
    } catch (e2) {
      console.error("Failed to create author", e2);
      setStatus(authorsStatusEl, "Create failed.", true);
      setError(`Failed to create author: ${extractApiErrorMessage(e2)}`);
    }
  });

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
    setStatus(seriesStatusEl, "Creating...", false);
    try {
      const created = await fetchJSONWithOptions("/api/v1/library/series/", {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrf },
        body: JSON.stringify({ name }),
      });
      state.allSeries.push(created);
      state.allSeries = uniqueById(state.allSeries);
      seriesNewNameEl.value = "";
      setStatus(seriesStatusEl, "Created.", false);
      syncSeriesSelectOptions({
        allSeries: state.allSeries,
        seriesSelectEl,
        selectedId: created && created.id ? String(created.id) : "",
      });
      if (state.book) state.book.series = created;
      rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
    } catch (e2) {
      console.error("Failed to create series", e2);
      setStatus(seriesStatusEl, "Create failed.", true);
      setError(`Failed to create series: ${extractApiErrorMessage(e2)}`);
    }
  });

  seriesSelectEl.addEventListener("change", () => {
    const sid = seriesSelectEl.value || "";
    if (state.book) {
      state.book.series = sid ? state.allSeries.find((s) => String(s.id) === String(sid)) : null;
    }
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
  });
  seriesIndexEl.addEventListener("input", () => {
    if (state.book) state.book.series_index = seriesIndexEl.value || null;
    rerenderHeader({ state, headerTitleEl, headerAuthorsEl, headerSeriesEl, headerFileEl });
  });
}
