import { fetchJSON } from "../api.js";
import { setGlobalError } from "../layout.js";
import { mountCovers } from "./covers.js";
import { setStatus } from "./status.js";

export function paginationContinuation(value, current, label) {
  if (value == null) return null;
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`Invalid ${label} pagination continuation.`);
  }
  const resolved = new URL(value, window.location.origin);
  const loaded = new URL(current, window.location.origin);
  if (resolved.origin !== window.location.origin) {
    throw new Error(`Invalid ${label} pagination continuation.`);
  }
  if (resolved.href === loaded.href) {
    throw new Error(`${label} pagination continuation repeated.`);
  }
  return value;
}

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
  onLoaded = null,
  loadErrorText = "Error loading.",
  clearResultsOnLoad = true,
  autoLoad = true,
}) {
  let nextUrl = null;
  let prevUrl = null;
  let currentUrl = initialUrl;

  let currentPayload = null;

  async function load(url, { reason = "load" } = {}) {
    if (!url || !resultsEl) return null;
    setStatus(statusEl, "Loading...", false);
    if (clearResultsOnLoad) resultsEl.innerHTML = "";
    if (nextBtn) nextBtn.disabled = true;
    if (prevBtn) prevBtn.disabled = true;

    try {
      const payload = await fetchJSON(url);
      if (!payload || !Array.isArray(payload.results)) {
        throw new Error("Invalid paginated response.");
      }
      const results = payload.results;
      resultsEl.innerHTML = render(payload, results, emptyText);
      mountCovers(resultsEl);

      nextUrl = paginationContinuation(payload.next, url, "next");
      prevUrl = paginationContinuation(payload.previous, url, "previous");
      currentUrl = url;
      currentPayload = payload;

      if (nextBtn) nextBtn.disabled = !nextUrl;
      if (prevBtn) prevBtn.disabled = !prevUrl;
      if (noteEl) {
        noteEl.textContent = formatNote ? formatNote(payload, results) : "";
      }

      const statusText = formatStatus
        ? formatStatus(payload, results, { url, reason })
        : results.length
          ? payload && payload.count != null
            ? `Showing ${results.length} of ${payload.count}.`
            : ""
          : emptyText;
      setStatus(statusEl, statusText, false);
      if (onLoaded) onLoaded(payload, results, { url, reason });
      return payload;
    } catch (error) {
      console.error("Failed to load paginated list", { url, error });
      if (error && error.status === 403) setStatus(statusEl, "Permission denied.", true);
      else if (error && error.status === 404) setStatus(statusEl, "Not found.", true);
      else setStatus(statusEl, loadErrorText, true);
      setGlobalError(loadErrorText);
      nextUrl = null;
      prevUrl = null;
      if (nextBtn) nextBtn.disabled = true;
      if (prevBtn) prevBtn.disabled = true;
      return null;
    }
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", async () => {
      if (nextUrl) await load(nextUrl, { reason: "next" });
    });
  }
  if (prevBtn) {
    prevBtn.addEventListener("click", async () => {
      if (prevUrl) await load(prevUrl, { reason: "previous" });
    });
  }

  const controller = {
    load,
    loadFirst: () => load(initialUrl),
    reload: () => load(currentUrl),
    reloadFirstPage: () => load(initialUrl),
    loadPrevious: (reason = "previous") =>
      prevUrl ? load(prevUrl, { reason }) : Promise.resolve(null),
    getState: () => ({
      currentUrl,
      nextUrl,
      previousUrl: prevUrl,
      resultCount: Array.isArray(currentPayload && currentPayload.results)
        ? currentPayload.results.length
        : 0,
    }),
  };
  if (autoLoad) await controller.loadFirst();
  return controller;
}
