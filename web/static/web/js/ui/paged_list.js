import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { setGlobalError } from "../layout.js";
import { mountCovers } from "./covers.js";
import { setStatus } from "./status.js";

export async function createPagedListController({
  statusEl,
  resultsEl,
  nextBtn,
  prevBtn,
  initialUrl,
  emptyText,
  render,
  noteEl = null,
  formatNote = null,
  formatStatus = null,
  clearResultsOnLoad = true,
  autoLoad = true,
}) {
  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = initialUrl;

  async function load(url) {
    if (!url || !resultsEl) return null;
    setStatus(statusEl, "Loading...", false);
    if (clearResultsOnLoad) resultsEl.innerHTML = "";
    if (nextBtn) nextBtn.disabled = true;
    if (prevBtn) prevBtn.disabled = true;

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      resultsEl.innerHTML = render(payload, results, emptyText);
      mountCovers(resultsEl);

      nextUrl = payload && payload.next ? String(payload.next) : null;
      prevUrl = payload && payload.previous ? String(payload.previous) : null;
      currentUrl = url;

      if (nextBtn) nextBtn.disabled = !nextUrl;
      if (prevBtn) prevBtn.disabled = !prevUrl;
      if (noteEl) {
        noteEl.textContent = formatNote ? formatNote(payload, results) : "";
      }

      const statusText = formatStatus
        ? formatStatus(payload, results)
        : results.length
          ? payload && payload.count != null
            ? `Showing ${results.length} of ${payload.count}.`
            : ""
          : emptyText;
      setStatus(statusEl, statusText, false);
      return payload;
    } catch (error) {
      console.error("Failed to load paginated list", { url, error });
      if (error && error.status === 403) setStatus(statusEl, "Permission denied.", true);
      else if (error && error.status === 404) setStatus(statusEl, "Not found.", true);
      else setStatus(statusEl, "Error loading.", true);
      setGlobalError(extractApiErrorMessage(error));
      nextUrl = null;
      prevUrl = null;
      if (nextBtn) nextBtn.disabled = true;
      if (prevBtn) prevBtn.disabled = true;
      return null;
    }
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", async () => {
      if (nextUrl) await load(nextUrl);
    });
  }
  if (prevBtn) {
    prevBtn.addEventListener("click", async () => {
      if (prevUrl) await load(prevUrl);
    });
  }

  const controller = {
    load,
    loadFirst: () => load(initialUrl),
    reload: () => load(currentUrl),
    reloadFirstPage: () => load(initialUrl),
  };
  if (autoLoad) await controller.loadFirst();
  return controller;
}
