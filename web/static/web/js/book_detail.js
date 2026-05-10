import { fetchJSON } from "./api.js";
import {
  $,
  escapeHtml,
  loadMeAndInitShell,
  setGlobalError,
  setGlobalErrorFromError,
  visible,
} from "./layout.js";

function setTitle(text) {
  const el = $("#book-title");
  if (!el) return;
  el.textContent = text;
}

function renderIdentifiers(identifiers) {
  if (!Array.isArray(identifiers) || identifiers.length === 0) {
    return '<div class="muted">No identifiers.</div>';
  }

  const items = identifiers
    .map((i) => {
      const scheme = i.scheme || "";
      const value = i.value || "";
      const source = i.source || "";
      const primary = i.is_primary ? ' <span class="pill">primary</span>' : "";
      return `<li><code>${escapeHtml(scheme)}</code>: ${escapeHtml(value)}${primary}${
        source ? ` <span class="muted">(${escapeHtml(source)})</span>` : ""
      }</li>`;
    })
    .join("");

  return `<ul>${items}</ul>`;
}

function renderFiles(files) {
  if (!Array.isArray(files) || files.length === 0) {
    return '<div class="muted">No files.</div>';
  }

  const items = files
    .map((f) => {
      const format = f.format ? String(f.format).toUpperCase() : "File";
      const size =
        f.file_size != null && f.file_size !== "" ? `${escapeHtml(f.file_size)} bytes` : "";
      const downloadUrl = f.download_url || "";
      const dl = downloadUrl ? `<a class="pill" href="${escapeHtml(downloadUrl)}">Download</a>` : "";
      return `<li><span class="pill">${escapeHtml(format)}</span> <span class="muted">${
        size ? size : ""
      }</span> ${dl}</li>`;
    })
    .join("");

  return `<ul>${items}</ul>`;
}

function renderSubjects(subjects) {
  if (!subjects) return "";
  if (Array.isArray(subjects)) {
    const clean = subjects.map((s) => String(s).trim()).filter(Boolean);
    if (!clean.length) return "";
    return clean.map((s) => `<span class="pill">${escapeHtml(s)}</span>`).join(" ");
  }
  if (typeof subjects === "string") {
    const s = subjects.trim();
    if (!s) return "";
    return `<span class="pill">${escapeHtml(s)}</span>`;
  }
  return "";
}

export async function initBookDetail() {
  const me = await loadMeAndInitShell();

  setGlobalError("");

  const statusEl = $("#book-status");
  const detailEl = $("#book-detail");
  const metaEl = $("#book-meta");
  const editWrapEl = $("#book-edit-link-wrap");
  const editLinkEl = $("#book-edit-link");
  const idSection = $("#book-identifiers");
  const idBody = $("#book-identifiers-body");
  const filesSection = $("#book-files");
  const filesBody = $("#book-files-body");
  const groupsSection = $("#book-groups");
  const groupsBody = $("#book-groups-body");

  if (
    !statusEl ||
    !detailEl ||
    !metaEl ||
    !editWrapEl ||
    !editLinkEl ||
    !idSection ||
    !idBody ||
    !filesSection ||
    !filesBody ||
    !groupsSection ||
    !groupsBody
  )
    return;

  const bookId = detailEl.dataset ? detailEl.dataset.bookId : "";
  if (!bookId) {
    statusEl.textContent = "Missing book id.";
    statusEl.classList.add("error");
    return;
  }

  const canManage = !!(me && me.capabilities && me.capabilities.can_manage_library);
  visible(editWrapEl, canManage);
  if (canManage) {
    editLinkEl.setAttribute(
      "href",
      `/library/books/${encodeURIComponent(String(bookId))}/edit/`
    );
  }

  function setStatus(text, isError) {
    statusEl.textContent = text;
    statusEl.classList.toggle("error", !!isError);
  }

  setStatus("Loading…", false);
  visible(detailEl, false);
  visible(idSection, false);
  visible(filesSection, false);
  visible(groupsSection, false);

  function renderBookGroups(groups) {
    if (!Array.isArray(groups) || groups.length === 0) {
      return '<div class="muted">No visible groups.</div>';
    }
    const items = groups
      .map((g) => {
        const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
        const badges = [g.is_public_group ? '<span class="pill pill--owner">Public</span>' : ""]
          .filter(Boolean)
          .join(" ");
        return `<li><a href="${escapeHtml(href)}">${escapeHtml(
          g.name || ""
        )}</a> <span class="muted"><code>${escapeHtml(g.slug || "")}</code></span> ${badges}</li>`;
      })
      .join("");
    return `<ul>${items}</ul>`;
  }

  try {
    const book = await fetchJSON(`/api/v1/library/books/${encodeURIComponent(String(bookId))}/`);

    const title = book.title || "Book";
    setTitle(title);

    const subtitle = book.subtitle ? book.subtitle : "";
    const authors = Array.isArray(book.authors) ? book.authors.map((a) => a.name).filter(Boolean) : [];
    const series = book.series && book.series.name ? book.series.name : "";
    const seriesIndex = book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
    const seriesLine = series ? `${series}${seriesIndex ? " · " + seriesIndex : ""}` : "";

    const subjectsHtml = renderSubjects(book.subjects);

    metaEl.innerHTML = `
        <div class="kv">
          <div class="kv__k">Title</div><div class="kv__v">${escapeHtml(title)}</div>
          ${subtitle ? `<div class="kv__k">Subtitle</div><div class="kv__v">${escapeHtml(subtitle)}</div>` : ""}
          <div class="kv__k">Authors</div><div class="kv__v">${escapeHtml(authors.join(", ") || "")}</div>
          ${seriesLine ? `<div class="kv__k">Series</div><div class="kv__v">${escapeHtml(seriesLine)}</div>` : ""}
          ${book.summary ? `<div class="kv__k">Summary</div><div class="kv__v">${escapeHtml(book.summary)}</div>` : ""}
          ${book.publisher ? `<div class="kv__k">Publisher</div><div class="kv__v">${escapeHtml(book.publisher)}</div>` : ""}
          ${book.language ? `<div class="kv__k">Language</div><div class="kv__v">${escapeHtml(book.language)}</div>` : ""}
          ${book.published_date ? `<div class="kv__k">Published</div><div class="kv__v">${escapeHtml(book.published_date)}</div>` : ""}
          ${book.isbn ? `<div class="kv__k">ISBN</div><div class="kv__v">${escapeHtml(book.isbn)}</div>` : ""}
          ${subjectsHtml ? `<div class="kv__k">Subjects</div><div class="kv__v">${subjectsHtml}</div>` : ""}
        </div>
      `.trim();

    idBody.innerHTML = renderIdentifiers(book.identifiers);
    filesBody.innerHTML = renderFiles(book.files);
    groupsBody.innerHTML = renderBookGroups(book.groups);

    visible(detailEl, true);
    visible(idSection, true);
    visible(filesSection, true);
    visible(groupsSection, true);
    setStatus("", false);
  } catch (e) {
    console.error("Failed to load book detail", { bookId, e });
    if (e && e.status === 404) {
      setStatus("Book not found or not accessible.", true);
    } else {
      setStatus("Error loading book.", true);
      setGlobalErrorFromError(e, "Failed to load book:");
    }
  }
}
