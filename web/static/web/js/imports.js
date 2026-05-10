import { fetchJSON, fetchJSONWithOptions, getCsrfToken, extractApiErrorMessage } from "./api.js";
import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "./layout.js";

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
      }${message ? ` <span class="muted">— ${escapeHtml(message)}</span>` : ""}</li>`;
    })
    .join("");

  const extra = items.length > 50 ? `<div class="muted">Showing first 50 items.</div>` : "";
  return `${extra}<ul>${rows}</ul>`;
}

function renderImportJobs(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((job) => {
      const message = job.message ? `<div class="muted">${escapeHtml(job.message)}</div>` : "";
      const createdAt = job.created_at ? `<div class="muted">${escapeHtml(job.created_at)}</div>` : "";
      const counts = [
        ["found", job.total_found],
        ["imported", job.imported_count],
        ["dupes", job.duplicate_count],
        ["failed", job.failed_count],
      ]
        .filter(([_k, v]) => v !== null && v !== undefined && v !== "")
        .map(([k, v]) => `<span class="pill">${escapeHtml(k)}: ${escapeHtml(v)}</span>`)
        .join(" ");

      const itemsHtml = renderImportJobItems(job.items);

      return `
          <article class="book">
            <h3 class="book__title">Job ${escapeHtml(job.id || "")}</h3>
            <div class="book__meta">
              <div>Source: ${escapeHtml(job.source_filename || "")} <span class="muted">(${escapeHtml(
        job.source_type || ""
      )})</span></div>
              <div>Status: <span class="pill">${escapeHtml(job.status || "")}</span></div>
              ${counts ? `<div>${counts}</div>` : ""}
              ${message}
              ${createdAt}
            </div>
            ${
              itemsHtml
                ? `<div class="card" style="margin-top: 10px;"><h4 class="card__title">Items</h4>${itemsHtml}</div>`
                : ""
            }
          </article>
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

  const caps = me && me.capabilities ? me.capabilities : {};
  const allowed = !!caps.can_access_imports;

  visible(notAllowedEl, !allowed);
  visible(uploadForm, allowed);

  let nextUrl = null;
  let prevUrl = null;
  const firstUrl = "/api/v1/library/imports/";

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  function setUploadStatus(text, isError) {
    uploadStatus.textContent = text || "\u00a0";
    uploadStatus.classList.toggle("error", !!isError);
  }

  async function load(url) {
    setGlobalError("");
    setStatus("Loading…", false);
    resultsEl.innerHTML = "";
    nextBtn.disabled = true;
    prevBtn.disabled = true;

    if (!allowed) {
      setStatus("Not allowed.", true);
      return;
    }

    try {
      const payload = await fetchJSON(url);
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) {
        setStatus("No import jobs yet.", false);
        nextUrl = null;
        prevUrl = null;
        return;
      }

      setStatus(payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "", false);
      resultsEl.innerHTML = renderImportJobs(payload);

      nextUrl = payload.next || null;
      prevUrl = payload.previous || null;
      nextBtn.disabled = !nextUrl;
      prevBtn.disabled = !prevUrl;
    } catch (e) {
      console.error("Failed to load import jobs", { url, e });
      setStatus("Error loading import jobs.", true);
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

    setUploadStatus("Uploading…", false);

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

      setUploadStatus("Upload complete. Refreshing jobs…", false);
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

