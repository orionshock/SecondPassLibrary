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
  seriesSelectEl,
  seriesIndexEl,
  headerTitleEl,
  headerAuthorsEl,
  headerSeriesEl,
  headerDownloadEl,
}) {
  authorsSelectedEl.addEventListener("click", (ev) => {
    const t = ev.target;
    if (!(t instanceof Element)) return;
    const button = t.closest("[data-remove-author-id]");
    const id = button ? button.getAttribute("data-remove-author-id") : "";
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

  seriesSelectEl.addEventListener("change", () => {
    const sid = seriesSelectEl.value || "";
    if (state.book) {
      state.book.series = sid ? state.allSeries.find((s) => String(s.id) === String(sid)) : null;
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
