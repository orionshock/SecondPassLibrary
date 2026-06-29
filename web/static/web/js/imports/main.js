import { fetchJSON, fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "../api.js";
import { canAccessImports } from "../auth.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";

function renderImportJobItems(items) {
  if (!Array.isArray(items) || items.length === 0) return "";
  const rows = items
    .slice(0, 50)
    .map((it) => {
      const status = it.status || "";
      const source = it.source_name || "";
      const message = it.message || "";
      const book = it.book ? `book=${it.book}` : "";
      const bookFile = it.book_file ? `book_file=${it.book_file}` : "";
      const refs = [book, bookFile].filter(Boolean).join(" ");
      return `<li><span class="pill">${escapeHtml(status)}</span> ${escapeHtml(source)}${
        refs ? ` <span class="muted">${escapeHtml(refs)}</span>` : ""
      }${message ? ` <span class="muted">- ${escapeHtml(message)}</span>` : ""}</li>`;
    })
    .join("");

  const extra = items.length > 50 ? `<div class="muted">Showing first 50 items.</div>` : "";
  return `${extra}<ul>${rows}</ul>`;
}

function friendlyDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function jobSourceLabel(job) {
  return job.source_filename || "(Unknown source)";
}

function jobCounts(job) {
  return [
    ["found", job.total_found],
    ["imported", job.imported_count],
    ["duplicates", job.duplicate_count],
    ["failed", job.failed_count],
  ].filter(([_k, v]) => v !== null && v !== undefined && v !== "");
}

function isActiveImportJob(job) {
  return ["pending", "processing"].includes(String(job.status || "").toLowerCase());
}

function renderImportJobs(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((job) => {
      const source = jobSourceLabel(job);
      const status = job.status || "";
      const message = job.message ? `<div class="muted">${escapeHtml(job.message)}</div>` : "";
      const createdAt = friendlyDate(job.created_at);
      const updatedAt = friendlyDate(job.updated_at);
      const counts = jobCounts(job)
        .map(([k, v]) => `<span class="pill">${escapeHtml(k)}: ${escapeHtml(v)}</span>`)
        .join(" ");

      const itemsHtml = renderImportJobItems(job.items);
      const open = isActiveImportJob(job) ? " open" : "";

      return `
          <details class="book import-job"${open}>
            <summary class="import-job__summary">
              <span class="import-job__source">${escapeHtml(source)}</span>
              <span class="pill">${escapeHtml(status)}</span>
              ${counts ? `<span class="import-job__counts">${counts}</span>` : ""}
              ${createdAt ? `<span class="muted import-job__time">Created ${escapeHtml(createdAt)}</span>` : ""}
              ${updatedAt ? `<span class="muted import-job__time">Updated ${escapeHtml(updatedAt)}</span>` : ""}
            </summary>
            <div class="book__meta import-job__details">
              <div>Job: <code>${escapeHtml(job.id || "")}</code></div>
              <div>Source type: ${escapeHtml(job.source_type || "")}</div>
              ${message}
              ${itemsHtml ? `<div class="import-job__items"><h4 class="card__title">Items</h4>${itemsHtml}</div>` : ""}
            </div>
          </details>
        `.trim();
    })
    .join("");
}

export async function initImports() {
  const me = await loadMeAndInitShell();

  const notAllowedEl = $("#imports-not-allowed");
  const uploadForm = $("#imports-upload");
  const uploadStatus = $("#imports-upload-status");
  const fileInput = $("#import-file");

  const statusEl = $("#imports-status");
  const resultsEl = $("#imports-results");
  const nextBtn = $("#imports-next");
  const prevBtn = $("#imports-prev");

  if (
    !statusEl ||
    !resultsEl ||
    !nextBtn ||
    !prevBtn ||
    !notAllowedEl ||
    !uploadForm ||
    !uploadStatus ||
    !fileInput
  ) {
    return;
  }

  const allowed = canAccessImports(me);

  visible(notAllowedEl, !allowed);
  visible(uploadForm, allowed);

  let nextUrl = null;
  let prevUrl = null;
  const firstUrl = "/api/v1/library/imports/";

  function setUploadStatus(text, isError) {
    uploadStatus.textContent = text || "\u00a0";
    uploadStatus.classList.toggle("error", !!isError);
  }

  async function load(url) {
    setGlobalError("");
    setStatus(statusEl, "Loading...", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    if (!allowed) {
      setStatus(statusEl, "Not allowed.", true);
      return;
    }

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) {
        setStatus(statusEl, "No import jobs yet.", false);
        nextUrl = null;
        prevUrl = null;
        return;
      }

      setStatus(
        statusEl,
        payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "",
        false
      );
      resultsEl.innerHTML = renderImportJobs(payload);

      nextUrl = payload.next || null;
      prevUrl = payload.previous || null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !prevUrl;
    } catch (e) {
      console.error("Failed to load import jobs", { url, e });
      setStatus(statusEl, "Error loading import jobs.", true);
      setGlobalError(extractApiErrorMessage(e));
      nextUrl = null;
      prevUrl = null;
    }
  }

  await load(firstUrl);

  nextBtn.addEventListener("click", async () => {
    if (nextUrl) await load(nextUrl);
  });
  prevBtn.addEventListener("click", async () => {
    if (prevUrl) await load(prevUrl);
  });

  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!allowed) return;

    const file = fileInput.files && fileInput.files.length ? fileInput.files[0] : null;
    if (!file) {
      setUploadStatus("Choose a file to upload.", true);
      return;
    }

    setUploadStatus("Uploading...", false);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const csrf = getCsrfToken();
      const headers = { Accept: "application/json" };
      if (csrf) headers["X-CSRFToken"] = csrf;

      const created = await fetchJSONWithOptions("/api/v1/library/imports/", {
        method: "POST",
        headers,
        body: formData,
      });

      setUploadStatus("Upload complete. Refreshing jobs...", false);
      if (created && created.id) {
        console.log("Created import job", created.id);
      }
      fileInput.value = "";
      await load(firstUrl);
      setUploadStatus("Ready.", false);
    } catch (e2) {
      console.error("Upload failed", e2);
      setUploadStatus(extractApiErrorMessage(e2), true);
      setGlobalError(extractApiErrorMessage(e2));
    }
  });
}
