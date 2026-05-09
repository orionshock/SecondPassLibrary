(function () {
  "use strict";

  function $(selector, root) {
    return (root || document).querySelector(selector);
  }

  function setGlobalError(message) {
    const el = $("#ui-global-error");
    if (!el) return;
    el.textContent = message || "";
    el.classList.toggle("is-hidden", !message);
  }

  function setGlobalErrorFromError(error, prefix) {
    const message = error && error.message ? String(error.message) : "Unknown error.";
    setGlobalError(prefix ? `${prefix} ${message}` : message);
  }

  function getCookie(name) {
    const cookies = document.cookie ? document.cookie.split(";") : [];
    for (const cookie of cookies) {
      const trimmed = cookie.trim();
      if (!trimmed) continue;
      if (trimmed.startsWith(name + "=")) {
        return decodeURIComponent(trimmed.slice(name.length + 1));
      }
    }
    return null;
  }

  function getCsrfToken() {
    return getCookie("csrftoken");
  }

  async function fetchJSON(url) {
    const response = await fetch(url, {
      method: "GET",
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    });

    const contentType = (response.headers.get("content-type") || "").toLowerCase();
    const isJson = contentType.includes("application/json");

    let bodyText = "";
    let bodyJson = null;

    if (isJson) {
      try {
        bodyJson = await response.json();
      } catch (e) {
        console.error("Failed to parse JSON response", { url, status: response.status, e });
        throw new Error(`Invalid JSON response (${response.status}).`);
      }
    } else {
      bodyText = await response.text().catch(() => "");
    }

    if (!response.ok) {
      const snippet = (bodyText || "").trim().slice(0, 160);
      const error = new Error(
        snippet
          ? `Request failed (${response.status}): ${snippet}`
          : `Request failed (${response.status}).`
      );
      error.status = response.status;
      error.body = isJson ? bodyJson : bodyText;
      throw error;
    }

    if (!isJson) {
      const snippet = (bodyText || "").trim().slice(0, 160);
      throw new Error(
        snippet
          ? `Expected JSON but received: ${snippet}`
          : "Expected JSON but received non-JSON response."
      );
    }

    return bodyJson;
  }

  async function fetchJSONWithOptions(url, options) {
    const response = await fetch(url, {
      credentials: "same-origin",
      ...options,
    });

    const contentType = (response.headers.get("content-type") || "").toLowerCase();
    const isJson = contentType.includes("application/json");

    let bodyText = "";
    let bodyJson = null;

    if (isJson) {
      try {
        bodyJson = await response.json();
      } catch (e) {
        console.error("Failed to parse JSON response", { url, status: response.status, e });
        throw new Error(`Invalid JSON response (${response.status}).`);
      }
    } else {
      bodyText = await response.text().catch(() => "");
    }

    if (!response.ok) {
      const snippet = (bodyText || "").trim().slice(0, 160);
      const error = new Error(
        snippet
          ? `Request failed (${response.status}): ${snippet}`
          : `Request failed (${response.status}).`
      );
      error.status = response.status;
      error.body = isJson ? bodyJson : bodyText;
      throw error;
    }

    return isJson ? bodyJson : bodyText;
  }

  function extractApiErrorMessage(error) {
    const body = error && error.body ? error.body : null;
    if (body && typeof body === "object") {
      if (body.error && typeof body.error === "object") {
        const code = body.error.code ? String(body.error.code) : "";
        const msg = body.error.message ? String(body.error.message) : "";
        if (code && msg) return `${code}: ${msg}`;
        if (msg) return msg;
        if (code) return code;
      }
      if (body.detail) return String(body.detail);
    }
    return error && error.message ? String(error.message) : "Unknown error.";
  }

  function setText(el, text) {
    if (!el) return;
    el.textContent = text;
  }

  function escapeHtml(value) {
    return String(value)
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function visible(el, on) {
    if (!el) return;
    el.classList.toggle("is-hidden", !on);
  }

  function setTitle(text) {
    const el = $("#book-title");
    if (!el) return;
    el.textContent = text;
  }

  function formatRole(role) {
    if (!role) return "";
    return role.charAt(0).toUpperCase() + role.slice(1);
  }

  function navShouldShowGroups(me) {
    if (!me) return false;
    const groups = Array.isArray(me.groups) ? me.groups : [];
    const caps = me.capabilities || {};
    return (
      groups.length > 0 ||
      !!caps.can_manage_library ||
      !!caps.can_create_library_groups ||
      !!caps.can_manage_group_memberships ||
      !!caps.can_manage_group_identity ||
      !!caps.can_edit_group_presentation
    );
  }

  function navShouldShowAdmin(me) {
    if (!me) return false;
    if (me.is_owner) return true;
    return me.role === "manager";
  }

  function updateNavVisibility(me) {
    const caps = me && me.capabilities ? me.capabilities : {};

    visible($('[data-nav="groups"]'), navShouldShowGroups(me));
    visible($('[data-nav="imports"]'), !!caps.can_access_imports);
    visible($('[data-nav="users"]'), !!caps.can_manage_users);
    visible($('[data-nav="admin"]'), navShouldShowAdmin(me));
  }

  function setActiveNav() {
    const path = window.location.pathname || "/";
    const mapping = [
      { key: "library", prefix: "/library/" },
      { key: "app", prefix: "/app/" },
      { key: "groups", prefix: "/groups/" },
      { key: "imports", prefix: "/imports/" },
      { key: "users", prefix: "/users/" },
      { key: "admin", prefix: "/admin/" },
    ];
    for (const { key, prefix } of mapping) {
      const el = $(`[data-nav="${key}"]`);
      if (!el) continue;
      const on = path === prefix || path.startsWith(prefix);
      if (on) el.setAttribute("aria-current", "page");
      else el.removeAttribute("aria-current");
    }
  }

  async function loadMeAndInitShell() {
    setActiveNav();

    try {
      const me = await fetchJSON("/api/v1/accounts/me/");
      setText($('[data-ui="username"]'), me.username || "User");
      updateNavVisibility(me);
      return me;
    } catch (e) {
      console.error("Failed to load /api/v1/accounts/me/", e);
      setText($('[data-ui="username"]'), "Error");
      setGlobalErrorFromError(e, "Failed to load identity:");
      return null;
    }
  }

  function renderGroups(groups) {
    if (!Array.isArray(groups) || groups.length === 0) {
      return '<div class="muted">No group memberships.</div>';
    }
    const items = groups
      .map((g) => {
        const bits = [];
        if (g.is_public_group) bits.push("Public");
        if (g.membership_role) bits.push(g.membership_role);
        return `<li><span>${escapeHtml(g.name)}</span> <span class="muted">(${escapeHtml(
          bits.join(", ") || "member"
        )})</span></li>`;
      })
      .join("");
    return `<ul>${items}</ul>`;
  }

  function renderCapabilities(caps) {
    const entries = caps && typeof caps === "object" ? Object.entries(caps) : [];
    if (entries.length === 0) return '<div class="muted">No capabilities.</div>';
    const items = entries
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([k, v]) => `<li><code>${escapeHtml(k)}</code>: ${v ? "yes" : "no"}</li>`)
      .join("");
    return `<ul>${items}</ul>`;
  }

  function sectionLinksForMe(me) {
    const caps = me && me.capabilities ? me.capabilities : {};
    const sections = [{ href: "/library/", label: "Library", visible: true }];
    sections.push({ href: "/groups/", label: "Groups", visible: navShouldShowGroups(me) });
    sections.push({ href: "/imports/", label: "Imports", visible: !!caps.can_access_imports });
    sections.push({ href: "/users/", label: "Users", visible: !!caps.can_manage_users });
    sections.push({ href: "/admin/", label: "Service Hatch", visible: navShouldShowAdmin(me) });
    return sections.filter((s) => s.visible);
  }

  async function initDashboard() {
    const me = await loadMeAndInitShell();
    if (!me) {
      setText($("#me-summary"), "Error loading identity.");
      setText($("#me-groups"), "Error loading identity.");
      setText($("#me-capabilities"), "Error loading identity.");
      setText($("#me-sections"), "Error loading identity.");
      return;
    }

    const ownerBadge = me.is_owner ? ' <span class="pill pill--owner">Owner</span>' : "";
    $("#me-summary").innerHTML = `
      <div class="kv">
        <div class="kv__k">Username</div><div class="kv__v">${escapeHtml(me.username || "")}${ownerBadge}</div>
        <div class="kv__k">Role</div><div class="kv__v">${escapeHtml(formatRole(me.role))}</div>
        <div class="kv__k">Email</div><div class="kv__v">${escapeHtml(me.email || "")}</div>
      </div>
    `.trim();

    $("#me-groups").innerHTML = renderGroups(me.groups);
    $("#me-capabilities").innerHTML = renderCapabilities(me.capabilities);

    const sections = sectionLinksForMe(me)
      .map((s) => `<a class="button" href="${escapeHtml(s.href)}">${escapeHtml(s.label)}</a>`)
      .join(" ");
    $("#me-sections").innerHTML = sections || '<div class="muted">No sections.</div>';
  }

  function bookFilesHtml(files) {
    if (!Array.isArray(files) || files.length === 0) return "";
    const links = files
      .filter((f) => f && f.download_url)
      .map((f) => {
        const label = f.format ? String(f.format).toUpperCase() : "Download";
        return `<a class="pill" href="${escapeHtml(f.download_url)}">${escapeHtml(label)}</a>`;
      })
      .join("");
    if (!links) return "";
    return `<div class="book__files">${links}</div>`;
  }

  function renderBooks(payload) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (results.length === 0) return "";

    return results
      .map((b) => {
        const title = b.title || "(Untitled)";
        const bookHref = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
        const subtitle = b.subtitle ? ` <span class="muted">— ${escapeHtml(b.subtitle)}</span>` : "";
        const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];
        const series = b.series && b.series.name ? b.series.name : "";
        const seriesIndex = b.series_index != null && b.series_index !== "" ? String(b.series_index) : "";
        const seriesLine = series ? `${series}${seriesIndex ? " · " + seriesIndex : ""}` : "";
        const language = b.language || "";

        const metaLines = [];
        if (authors.length) metaLines.push(`<div>${escapeHtml(authors.join(", "))}</div>`);
        if (seriesLine) metaLines.push(`<div>${escapeHtml(seriesLine)}</div>`);
        if (language) metaLines.push(`<div>Language: ${escapeHtml(language)}</div>`);

        return `
          <article class="book">
            <h3 class="book__title">${
              bookHref
                ? `<a href="${escapeHtml(bookHref)}">${escapeHtml(title)}</a>${subtitle}`
                : `${escapeHtml(title)}${subtitle}`
            }</h3>
            <div class="book__meta">${metaLines.join("") || '<div class="muted">No metadata.</div>'}</div>
            ${bookFilesHtml(b.files)}
          </article>
        `.trim();
      })
      .join("");
  }

  function urlWithParams(base, params) {
    const url = new URL(base, window.location.origin);
    for (const [k, v] of Object.entries(params || {})) {
      if (v === null || v === undefined || v === "") continue;
      url.searchParams.set(k, String(v));
    }
    return url.toString();
  }

  async function initLibraryBrowse() {
    await loadMeAndInitShell();

    const statusEl = $("#library-status");
    const resultsEl = $("#library-results");
    const nextBtn = $("#next");
    const prevBtn = $("#prev");
    const form = $("#library-search");
    const qInput = $("#q");

    if (!statusEl || !resultsEl || !nextBtn || !prevBtn || !form || !qInput) return;

    let nextUrl = null;
    let prevUrl = null;

    function setStatus(text, isError) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", !!isError);
    }

    async function load(url) {
      setStatus("Loading…", false);
      resultsEl.innerHTML = "";
      nextBtn.disabled = true;
      prevBtn.disabled = true;

      try {
        const payload = await fetchJSON(url);
        const hasAny = payload && payload.count ? payload.count > 0 : Array.isArray(payload.results) && payload.results.length > 0;

        if (!hasAny) {
          setStatus("Empty library.", false);
          nextUrl = null;
          prevUrl = null;
          return;
        }

        setStatus("", false);
        resultsEl.innerHTML = renderBooks(payload);

        nextUrl = payload.next || null;
        prevUrl = payload.previous || null;
        nextBtn.disabled = !nextUrl;
        prevBtn.disabled = !prevUrl;
      } catch (e) {
        console.error("Failed to load books", { url, e });
        setStatus("Error loading data.", true);
        setGlobalErrorFromError(e, "Failed to load library:");
        nextUrl = null;
        prevUrl = null;
      }
    }

    function syncQueryFromLocation() {
      const params = new URLSearchParams(window.location.search);
      qInput.value = params.get("q") || "";
    }

    function pushLocation(params) {
      const url = new URL(window.location.href);
      url.search = new URLSearchParams(params).toString();
      window.history.pushState({}, "", url.toString());
    }

    syncQueryFromLocation();
    const initialQ = new URLSearchParams(window.location.search).get("q") || "";
    await load(urlWithParams("/api/v1/library/books/", { q: initialQ }));

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = (qInput.value || "").trim();
      pushLocation(q ? { q } : {});
      await load(urlWithParams("/api/v1/library/books/", { q }));
    });

    nextBtn.addEventListener("click", async () => {
      if (nextUrl) await load(nextUrl);
    });
    prevBtn.addEventListener("click", async () => {
      if (prevUrl) await load(prevUrl);
    });

    window.addEventListener("popstate", async () => {
      syncQueryFromLocation();
      const q = (qInput.value || "").trim();
      await load(urlWithParams("/api/v1/library/books/", { q }));
    });
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
        const size = f.file_size != null && f.file_size !== "" ? `${escapeHtml(f.file_size)} bytes` : "";
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

  async function initBookDetail() {
    await loadMeAndInitShell();

    setGlobalError("");

    const statusEl = $("#book-status");
    const detailEl = $("#book-detail");
    const metaEl = $("#book-meta");
    const idSection = $("#book-identifiers");
    const idBody = $("#book-identifiers-body");
    const filesSection = $("#book-files");
    const filesBody = $("#book-files-body");

    if (!statusEl || !detailEl || !metaEl || !idSection || !idBody || !filesSection || !filesBody) return;

    const bookId = detailEl.dataset ? detailEl.dataset.bookId : "";
    if (!bookId) {
      statusEl.textContent = "Missing book id.";
      statusEl.classList.add("error");
      return;
    }

    function setStatus(text, isError) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", !!isError);
    }

    setStatus("Loading…", false);
    visible(detailEl, false);
    visible(idSection, false);
    visible(filesSection, false);

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

      visible(detailEl, true);
      visible(idSection, true);
      visible(filesSection, true);
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

    const extra =
      items.length > 50 ? `<div class="muted">Showing first 50 items.</div>` : "";
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
              <div>Source: ${escapeHtml(job.source_filename || "")} <span class="muted">(${escapeHtml(job.source_type || "")})</span></div>
              <div>Status: <span class="pill">${escapeHtml(job.status || "")}</span></div>
              ${counts ? `<div>${counts}</div>` : ""}
              ${message}
              ${createdAt}
            </div>
            ${itemsHtml ? `<div class="card" style="margin-top: 10px;"><h4 class="card__title">Items</h4>${itemsHtml}</div>` : ""}
          </article>
        `.trim();
      })
      .join("");
  }

  async function initImports() {
    const me = await loadMeAndInitShell();

    const notAllowedEl = $("#imports-not-allowed");
    const uploadForm = $("#imports-upload");
    const uploadStatus = $("#imports-upload-status");
    const fileInput = $("#import-file");

    const statusEl = $("#imports-status");
    const resultsEl = $("#imports-results");
    const nextBtn = $("#imports-next");
    const prevBtn = $("#imports-prev");

    if (!statusEl || !resultsEl || !nextBtn || !prevBtn || !notAllowedEl || !uploadForm || !uploadStatus || !fileInput) {
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

  function renderGroupsList(payload) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (results.length === 0) return "";

    return results
      .map((g) => {
        const name = g.name || "";
        const slug = g.slug || "";
        const discoverability = g.discoverability || "";
        const membershipRole = g.membership_role || "";
        const isPublic = !!g.is_public_group;
        const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";

        const badges = [
          isPublic ? '<span class="pill pill--owner">Public</span>' : "",
          discoverability ? `<span class="pill">${escapeHtml(discoverability)}</span>` : "",
          membershipRole ? `<span class="pill">${escapeHtml(membershipRole)}</span>` : "",
        ]
          .filter(Boolean)
          .join(" ");

        return `
          <article class="book">
            <h3 class="book__title"><a href="${escapeHtml(href)}">${escapeHtml(name)}</a></h3>
            <div class="book__meta">
              <div>Slug: <code>${escapeHtml(slug)}</code></div>
              ${badges ? `<div>${badges}</div>` : ""}
            </div>
          </article>
        `.trim();
      })
      .join("");
  }

  async function initGroupsList() {
    await loadMeAndInitShell();
    setGlobalError("");

    const statusEl = $("#groups-status");
    const resultsEl = $("#groups-results");
    const nextBtn = $("#groups-next");
    const prevBtn = $("#groups-prev");
    if (!statusEl || !resultsEl || !nextBtn || !prevBtn) return;

    let nextUrl = null;
    let prevUrl = null;

    function setStatus(text, isError) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", !!isError);
    }

    async function load(url) {
      setStatus("Loading…", false);
      resultsEl.innerHTML = "";
      nextBtn.disabled = true;
      prevBtn.disabled = true;

      try {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        if (results.length === 0) {
          setStatus("No groups.", false);
          nextUrl = null;
          prevUrl = null;
          return;
        }

        setStatus(payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "", false);
        resultsEl.innerHTML = renderGroupsList(payload);

        nextUrl = payload.next || null;
        prevUrl = payload.previous || null;
        nextBtn.disabled = !nextUrl;
        prevBtn.disabled = !prevUrl;
      } catch (e) {
        console.error("Failed to load groups", { url, e });
        if (e && e.status === 403) {
          setStatus("Permission denied.", true);
        } else if (e && e.status === 404) {
          setStatus("Not found.", true);
        } else {
          setStatus("Error loading groups.", true);
        }
        setGlobalError(extractApiErrorMessage(e));
        nextUrl = null;
        prevUrl = null;
      }
    }

    await load("/api/v1/library/groups/");

    nextBtn.addEventListener("click", async () => {
      if (nextUrl) await load(nextUrl);
    });
    prevBtn.addEventListener("click", async () => {
      if (prevUrl) await load(prevUrl);
    });
  }

  function renderGroupBooks(payload, groupId) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (results.length === 0) return "";

    return results
      .map((b) => {
        const title = b.title || "(Untitled)";
        const subtitle = b.subtitle ? ` <span class="muted">— ${escapeHtml(b.subtitle)}</span>` : "";
        const bookHref = b.id ? `/library/books/${encodeURIComponent(String(b.id))}/` : null;
        const authors = Array.isArray(b.authors) ? b.authors.map((a) => a.name).filter(Boolean) : [];

        const removeBtn =
          b.id && groupId
            ? `<button class="button" type="button" data-action="remove-book" data-book-id="${escapeHtml(b.id)}">Remove from group</button>`
            : "";

        return `
          <article class="book">
            <h3 class="book__title">${
              bookHref
                ? `<a href="${escapeHtml(bookHref)}">${escapeHtml(title)}</a>${subtitle}`
                : `${escapeHtml(title)}${subtitle}`
            }</h3>
            <div class="book__meta">
              ${authors.length ? `<div>${escapeHtml(authors.join(", "))}</div>` : ""}
            </div>
            ${removeBtn ? `<div style="margin-top: 10px;">${removeBtn}</div>` : ""}
          </article>
        `.trim();
      })
      .join("");
  }

  async function initGroupDetail() {
    await loadMeAndInitShell();
    setGlobalError("");

    const summaryEl = $("#group-summary");
    const statusEl = $("#group-status");
    const titleEl = $("#group-title");
    const metaEl = $("#group-meta");

    const editSection = $("#group-edit");
    const editForm = $("#group-edit-form");
    const editStatus = $("#group-edit-status");
    const descInput = $("#group-description");
    const discSelect = $("#group-discoverability");
    const discNote = $("#group-discoverability-note");

    const booksSection = $("#group-books");
    const booksStatus = $("#group-books-status");
    const booksResults = $("#group-books-results");
    const booksNext = $("#group-books-next");
    const booksPrev = $("#group-books-prev");

    const addBookForm = $("#group-add-book");
    const addBookInput = $("#group-book-id");
    const addBookStatus = $("#group-add-book-status");

    if (
      !summaryEl ||
      !statusEl ||
      !titleEl ||
      !metaEl ||
      !editSection ||
      !editForm ||
      !editStatus ||
      !descInput ||
      !discSelect ||
      !discNote ||
      !booksSection ||
      !booksStatus ||
      !booksResults ||
      !booksNext ||
      !booksPrev ||
      !addBookForm ||
      !addBookInput ||
      !addBookStatus
    ) {
      return;
    }

    const groupId = summaryEl.dataset ? summaryEl.dataset.groupId : "";
    if (!groupId) {
      statusEl.textContent = "Missing group id.";
      statusEl.classList.add("error");
      return;
    }

    let isPublicGroup = false;
    let booksNextUrl = null;
    let booksPrevUrl = null;

    function setStatus(text, isError) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", !!isError);
    }

    function setBooksStatus(text, isError) {
      booksStatus.textContent = text;
      booksStatus.classList.toggle("error", !!isError);
    }

    function setEditStatus(text, isError) {
      editStatus.textContent = text || "";
      editStatus.classList.toggle("error", !!isError);
    }

    function setAddBookStatus(text, isError) {
      addBookStatus.textContent = text || "";
      addBookStatus.classList.toggle("error", !!isError);
    }

    async function loadGroup() {
      setStatus("Loading…", false);
      visible(summaryEl, false);
      visible(editSection, false);
      visible(booksSection, false);

      try {
        const group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
        const name = group.name || "Group";
        titleEl.textContent = name;

        isPublicGroup = !!group.is_public_group;
        const membershipRole = group.membership_role || "";

        const badges = [
          isPublicGroup ? '<span class="pill pill--owner">Public</span>' : "",
          group.discoverability ? `<span class="pill">${escapeHtml(group.discoverability)}</span>` : "",
          membershipRole ? `<span class="pill">${escapeHtml(membershipRole)}</span>` : "",
        ]
          .filter(Boolean)
          .join(" ");

        metaEl.innerHTML = `
          <div class="kv">
            <div class="kv__k">Name</div><div class="kv__v">${escapeHtml(name)}</div>
            <div class="kv__k">Slug</div><div class="kv__v"><code>${escapeHtml(group.slug || "")}</code></div>
            <div class="kv__k">Badges</div><div class="kv__v">${badges || ""}</div>
            <div class="kv__k">Description</div><div class="kv__v">${escapeHtml(group.description || "")}</div>
          </div>
        `.trim();

        descInput.value = group.description || "";
        discSelect.value = group.discoverability || "listed";
        if (isPublicGroup) {
          discSelect.disabled = true;
          discNote.textContent = "Public discoverability cannot be changed.";
        } else {
          discSelect.disabled = false;
          discNote.textContent = "";
        }

        visible(summaryEl, true);
        visible(editSection, true);
        visible(booksSection, true);
        setStatus("", false);
      } catch (e) {
        console.error("Failed to load group", { groupId, e });
        if (e && e.status === 404) setStatus("Not found or not accessible.", true);
        else if (e && e.status === 403) setStatus("Permission denied.", true);
        else setStatus("Error loading group.", true);
        setGlobalError(extractApiErrorMessage(e));
      }
    }

    async function loadBooks(url) {
      setBooksStatus("Loading…", false);
      booksResults.innerHTML = "";
      booksNext.disabled = true;
      booksPrev.disabled = true;

      try {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        if (results.length === 0) {
          setBooksStatus("No books in this group.", false);
          booksNextUrl = null;
          booksPrevUrl = null;
          return;
        }

        setBooksStatus(payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "", false);
        booksResults.innerHTML = renderGroupBooks(payload, groupId);
        booksNextUrl = payload.next || null;
        booksPrevUrl = payload.previous || null;
        booksNext.disabled = !booksNextUrl;
        booksPrev.disabled = !booksPrevUrl;
      } catch (e) {
        console.error("Failed to load group books", { groupId, url, e });
        if (e && e.status === 404) setBooksStatus("Not found.", true);
        else if (e && e.status === 403) setBooksStatus("Permission denied.", true);
        else setBooksStatus("Error loading group books.", true);
        setGlobalError(extractApiErrorMessage(e));
        booksNextUrl = null;
        booksPrevUrl = null;
      }
    }

    async function refreshBooksFirstPage() {
      await loadBooks(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`);
    }

    booksNext.addEventListener("click", async () => {
      if (booksNextUrl) await loadBooks(booksNextUrl);
    });
    booksPrev.addEventListener("click", async () => {
      if (booksPrevUrl) await loadBooks(booksPrevUrl);
    });

    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setEditStatus("Saving…", false);
      setGlobalError("");

      const payload = {
        description: descInput.value || "",
      };
      if (!isPublicGroup) payload.discoverability = discSelect.value;

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(payload),
        });

        setEditStatus("Saved.", false);
        await loadGroup();
      } catch (e2) {
        console.error("Failed to save group presentation", { groupId, e2 });
        if (e2 && e2.status === 403) setEditStatus("Permission denied.", true);
        else setEditStatus("Save failed.", true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });

    addBookForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setAddBookStatus("Adding…", false);
      setGlobalError("");

      const bookId = (addBookInput.value || "").trim();
      if (!bookId) {
        setAddBookStatus("Enter a book UUID.", true);
        return;
      }

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`, {
          method: "POST",
          headers,
          body: JSON.stringify({ book: bookId }),
        });

        setAddBookStatus("Added.", false);
        addBookInput.value = "";
        await refreshBooksFirstPage();
      } catch (e2) {
        console.error("Failed to add book to group", { groupId, bookId, e2 });
        if (e2 && e2.status === 403) setAddBookStatus("Permission denied.", true);
        else setAddBookStatus("Add failed.", true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });

    booksResults.addEventListener("click", async (e) => {
      const target = e.target;
      if (!target || target.nodeType !== 1) return;
      if (target.getAttribute("data-action") !== "remove-book") return;

      const bookId = target.getAttribute("data-book-id");
      if (!bookId) return;

      setGlobalError("");
      setBooksStatus("Removing…", false);

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(
          `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/${encodeURIComponent(String(bookId))}/`,
          { method: "DELETE", headers }
        );

        await refreshBooksFirstPage();
      } catch (e2) {
        console.error("Failed to remove book from group", { groupId, bookId, e2 });
        if (e2 && e2.status === 403) setBooksStatus("Permission denied.", true);
        else setBooksStatus("Remove failed.", true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });

    await loadGroup();
    await refreshBooksFirstPage();
  }

  window.SecondPassUI = {
    initDashboard,
    initLibraryBrowse,
    initBookDetail,
    initImports,
    initGroupsList,
    initGroupDetail,
    getCsrfToken,
  };

  document.addEventListener("DOMContentLoaded", () => {
    const page = document.body && document.body.dataset ? document.body.dataset.page : "";
    if (page === "app") {
      initDashboard().catch((e) => {
        console.error("initDashboard failed", e);
        setGlobalErrorFromError(e, "App error:");
      });
    } else if (page === "library") {
      initLibraryBrowse().catch((e) => {
        console.error("initLibraryBrowse failed", e);
        setGlobalErrorFromError(e, "Library error:");
      });
    } else if (page === "book-detail") {
      initBookDetail().catch((e) => {
        console.error("initBookDetail failed", e);
        setGlobalErrorFromError(e, "Book error:");
      });
    } else if (page === "imports") {
      initImports().catch((e) => {
        console.error("initImports failed", e);
        setGlobalErrorFromError(e, "Imports error:");
      });
    } else if (page === "groups") {
      initGroupsList().catch((e) => {
        console.error("initGroupsList failed", e);
        setGlobalErrorFromError(e, "Groups error:");
      });
    } else if (page === "group-detail") {
      initGroupDetail().catch((e) => {
        console.error("initGroupDetail failed", e);
        setGlobalErrorFromError(e, "Group error:");
      });
    } else {
      loadMeAndInitShell().catch((e) => {
        console.error("Shell init failed", e);
        setGlobalErrorFromError(e, "UI error:");
      });
    }
  });
})();
