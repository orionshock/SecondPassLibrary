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
      setText($("#me-edit-status"), "Error loading identity.");
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
        <div class="kv__k">Email</div><div class="kv__v" id="me-email">${escapeHtml(me.email || "")}</div>
      </div>
    `.trim();

    $("#me-groups").innerHTML = renderGroups(me.groups);
    $("#me-capabilities").innerHTML = renderCapabilities(me.capabilities);

    const sections = sectionLinksForMe(me)
      .map((s) => `<a class="button" href="${escapeHtml(s.href)}">${escapeHtml(s.label)}</a>`)
      .join(" ");
    $("#me-sections").innerHTML = sections || '<div class="muted">No sections.</div>';

    const form = $("#me-edit-form");
    const emailInput = $("#me-edit-email");
    const firstInput = $("#me-edit-first");
    const lastInput = $("#me-edit-last");
    const statusEl = $("#me-edit-status");

    if (form && emailInput && firstInput && lastInput && statusEl) {
      // Email comes from /me/ payload; names are server-rendered in the template.
      emailInput.value = me.email || "";
      statusEl.textContent = "";
      statusEl.classList.remove("error");

      if (!form.dataset.bound) {
        form.dataset.bound = "1";
        form.dataset.baseEmail = emailInput.value || "";
        form.dataset.baseFirst = firstInput.value || "";
        form.dataset.baseLast = lastInput.value || "";
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          setGlobalError("");
          statusEl.textContent = "Saving…";
          statusEl.classList.remove("error");

          const desired = {
            email: (emailInput.value || "").trim(),
            first_name: (firstInput.value || "").trim(),
            last_name: (lastInput.value || "").trim(),
          };

          const patch = {};
          if (String(desired.email) !== String(form.dataset.baseEmail || "")) patch.email = desired.email;
          if (String(desired.first_name) !== String(form.dataset.baseFirst || "")) patch.first_name = desired.first_name;
          if (String(desired.last_name) !== String(form.dataset.baseLast || "")) patch.last_name = desired.last_name;

          if (Object.keys(patch).length === 0) {
            statusEl.textContent = "No changes.";
            return;
          }

          try {
            const csrf = getCsrfToken();
            const headers = { Accept: "application/json", "Content-Type": "application/json" };
            if (csrf) headers["X-CSRFToken"] = csrf;

            await fetchJSONWithOptions("/api/v1/accounts/me/", {
              method: "PATCH",
              headers,
              body: JSON.stringify(patch),
            });

            statusEl.textContent = "Saved.";
            form.dataset.baseEmail = desired.email;
            form.dataset.baseFirst = desired.first_name;
            form.dataset.baseLast = desired.last_name;
            const emailEl = $("#me-email");
            if (emailEl) emailEl.textContent = desired.email;
          } catch (e2) {
            console.error("Failed to save /api/v1/accounts/me/", e2);
            const msg = extractApiErrorMessage(e2);
            statusEl.textContent = msg;
            statusEl.classList.add("error");
            setGlobalError(msg);
          }
        });
      }
    }
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
    const groupsSection = $("#book-groups");
    const groupsBody = $("#book-groups-body");

    if (!statusEl || !detailEl || !metaEl || !idSection || !idBody || !filesSection || !filesBody || !groupsSection || !groupsBody) return;

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
    visible(groupsSection, false);

    function renderBookGroups(groups) {
      if (!Array.isArray(groups) || groups.length === 0) {
        return '<div class="muted">No visible groups.</div>';
      }
      const items = groups
        .map((g) => {
          const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
          const badges = [
            g.is_public_group ? '<span class="pill pill--owner">Public</span>' : "",
          ]
            .filter(Boolean)
            .join(" ");
          return `<li><a href="${escapeHtml(href)}">${escapeHtml(g.name || "")}</a> <span class="muted"><code>${escapeHtml(g.slug || "")}</code></span> ${badges}</li>`;
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
        const membershipRole = g.membership_role || "";
        const isPublic = !!g.is_public_group;
        const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";

        const badges = [
          isPublic ? '<span class="pill pill--owner">Public</span>' : "",
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
    const me = await loadMeAndInitShell();
    setGlobalError("");

    const summaryEl = $("#group-summary");
    const statusEl = $("#group-status");
    const titleEl = $("#group-title");
    const metaEl = $("#group-meta");

    const editSection = $("#group-edit");
    const editForm = $("#group-edit-form");
    const editStatus = $("#group-edit-status");
    const descInput = $("#group-description");
    const discSelect = null;
    const discNote = null;

    const booksSection = $("#group-books");
    const booksStatus = $("#group-books-status");
    const booksResults = $("#group-books-results");
    const booksNext = $("#group-books-next");
    const booksPrev = $("#group-books-prev");

    const addBookForm = $("#group-add-book");
    const addBookInput = $("#group-book-id");
    const addBookStatus = $("#group-add-book-status");

    const membersSection = $("#group-members");
    const membersNote = $("#group-members-note");
    const membersStatus = $("#group-members-status");
    const membersResults = $("#group-members-results");
    const membersNext = $("#group-members-next");
    const membersPrev = $("#group-members-prev");

    const addMemberForm = $("#group-add-member");
    const addMemberUser = $("#group-member-user");
    const addMemberRole = $("#group-member-role");
    const addMemberStatus = $("#group-add-member-status");

    if (
      !summaryEl ||
      !statusEl ||
      !titleEl ||
      !metaEl ||
      !editSection ||
      !editForm ||
      !editStatus ||
      !descInput ||
      !booksSection ||
      !booksStatus ||
      !booksResults ||
      !booksNext ||
      !booksPrev ||
      !addBookForm ||
      !addBookInput ||
      !addBookStatus ||
      !membersSection ||
      !membersNote ||
      !membersStatus ||
      !membersResults ||
      !membersNext ||
      !membersPrev ||
      !addMemberForm ||
      !addMemberUser ||
      !addMemberRole ||
      !addMemberStatus
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
    let membersNextUrl = null;
    let membersPrevUrl = null;
    const canManageMemberships = !!(me && me.capabilities && me.capabilities.can_manage_group_memberships);

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

    function setMembersStatus(text, isError) {
      membersStatus.textContent = text;
      membersStatus.classList.toggle("error", !!isError);
    }

    function setAddMemberStatus(text, isError) {
      addMemberStatus.textContent = text || "";
      addMemberStatus.classList.toggle("error", !!isError);
    }

    function renderMemberships(payload) {
      const results = Array.isArray(payload && payload.results) ? payload.results : [];
      if (results.length === 0) return "";

      return results
        .map((m) => {
          const isOwner = !!m.is_owner;
          const role = m.role || "reader";
          const removeDisabled = isPublicGroup ? "disabled" : "";
          const curatorDisabled = isPublicGroup ? "disabled" : "";

          const ownerBadge = isOwner ? ' <span class="pill pill--owner">Owner</span>' : "";
          const note = isPublicGroup ? '<div class="muted">Public memberships cannot be removed; role remains reader.</div>' : "";

          return `
            <article class="book">
              <h3 class="book__title">${escapeHtml(m.username || "")}${ownerBadge}</h3>
              <div class="book__meta">
                ${m.email ? `<div>${escapeHtml(m.email)}</div>` : ""}
                <div>Role: <select data-action="member-role" data-membership-id="${escapeHtml(m.id)}">
                  <option value="reader" ${role === "reader" ? "selected" : ""}>reader</option>
                  <option value="curator" ${role === "curator" ? "selected" : ""} ${curatorDisabled}>curator</option>
                </select></div>
                ${note}
              </div>
              <div style="margin-top: 10px; display: flex; gap: 8px; flex-wrap: wrap;">
                <button class="button" type="button" data-action="member-save" data-membership-id="${escapeHtml(m.id)}">Save role</button>
                <button class="button" type="button" data-action="member-remove" data-membership-id="${escapeHtml(m.id)}" ${removeDisabled}>Remove</button>
              </div>
            </article>
          `.trim();
        })
        .join("");
    }

    async function loadAllManageableUsers() {
      // Uses Manager/Owner users endpoint; fetch a few pages to populate a dropdown.
      const users = [];
      let url = "/api/v1/accounts/users/";
      for (let i = 0; i < 10 && url; i++) {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        for (const u of results) users.push(u);
        url = payload.next || null;
      }
      return users;
    }

    async function loadMembers(url) {
      setMembersStatus("Loading…", false);
      membersResults.innerHTML = "";
      membersNext.disabled = true;
      membersPrev.disabled = true;

      try {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        if (results.length === 0) {
          setMembersStatus("No members.", false);
          membersNextUrl = null;
          membersPrevUrl = null;
          return;
        }

        setMembersStatus(
          payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "",
          false
        );
        membersResults.innerHTML = renderMemberships(payload);
        membersNextUrl = payload.next || null;
        membersPrevUrl = payload.previous || null;
        membersNext.disabled = !membersNextUrl;
        membersPrev.disabled = !membersPrevUrl;
      } catch (e) {
        console.error("Failed to load memberships", { groupId, url, e });
        if (e && e.status === 403) setMembersStatus("Permission denied.", true);
        else if (e && e.status === 404) setMembersStatus("Not found.", true);
        else setMembersStatus("Error loading members.", true);
        setGlobalError(extractApiErrorMessage(e));
        membersNextUrl = null;
        membersPrevUrl = null;
      }
    }

    async function refreshMembersFirstPage() {
      await loadMembers(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`);
    }

    async function loadGroup() {
      setStatus("Loading…", false);
      visible(summaryEl, false);
      visible(editSection, false);
      visible(booksSection, false);
      visible(membersSection, false);

      try {
        const group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
        const name = group.name || "Group";
        titleEl.textContent = name;

        isPublicGroup = !!group.is_public_group;
        const membershipRole = group.membership_role || "";

        const badges = [
          isPublicGroup ? '<span class="pill pill--owner">Public</span>' : "",
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
        // discoverability removed

        visible(summaryEl, true);
        visible(editSection, true);
        visible(booksSection, true);

        // Membership management is Manager/Owner only.
        if (canManageMemberships) {
          visible(membersSection, true);
          if (isPublicGroup) {
            membersNote.textContent = "Public membership is required for all users. It cannot be removed, and cannot have curators.";
            addMemberRole.value = "reader";
            addMemberRole.querySelector('option[value="curator"]').disabled = true;
          } else {
            membersNote.textContent = "";
            addMemberRole.querySelector('option[value="curator"]').disabled = false;
          }
        } else {
          visible(membersSection, false);
        }

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

    membersNext.addEventListener("click", async () => {
      if (membersNextUrl) await loadMembers(membersNextUrl);
    });
    membersPrev.addEventListener("click", async () => {
      if (membersPrevUrl) await loadMembers(membersPrevUrl);
    });

    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setEditStatus("Saving…", false);
      setGlobalError("");

      const payload = {
        description: descInput.value || "",
      };
      // discoverability removed

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

    if (canManageMemberships) {
      // Populate add-member dropdown and load current memberships.
      try {
        const users = await loadAllManageableUsers();
        addMemberUser.innerHTML = users
          .map((u) => `<option value="${escapeHtml(u.id)}">${escapeHtml(u.username)} (${escapeHtml(u.email || "")})</option>`)
          .join("");
        visible(addMemberForm, true);
      } catch (e) {
        console.error("Failed to load manageable users for membership add", e);
        visible(addMemberForm, true);
        addMemberUser.innerHTML = "";
        setAddMemberStatus("Error loading user list.", true);
      }

      await refreshMembersFirstPage();

      addMemberForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        setAddMemberStatus("Adding…", false);
        setGlobalError("");

        const userId = addMemberUser.value;
        const role = isPublicGroup ? "reader" : addMemberRole.value;
        if (!userId) {
          setAddMemberStatus("Choose a user.", true);
          return;
        }

        try {
          const csrf = getCsrfToken();
          const headers = { Accept: "application/json", "Content-Type": "application/json" };
          if (csrf) headers["X-CSRFToken"] = csrf;

          await fetchJSONWithOptions(
            `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
            { method: "POST", headers, body: JSON.stringify({ user: Number(userId), role }) }
          );

          setAddMemberStatus("Added.", false);
          await refreshMembersFirstPage();
        } catch (e2) {
          console.error("Failed to add member", { groupId, e2 });
          setAddMemberStatus(extractApiErrorMessage(e2), true);
          setGlobalError(extractApiErrorMessage(e2));
        }
      });

      membersResults.addEventListener("click", async (e) => {
        const target = e.target;
        if (!target || target.nodeType !== 1) return;
        const action = target.getAttribute("data-action");
        const membershipId = target.getAttribute("data-membership-id");
        if (!action || !membershipId) return;

        if (action === "member-remove") {
          setMembersStatus("Removing…", false);
          try {
            const csrf = getCsrfToken();
            const headers = { Accept: "application/json" };
            if (csrf) headers["X-CSRFToken"] = csrf;

            await fetchJSONWithOptions(
              `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
              { method: "DELETE", headers }
            );
            await refreshMembersFirstPage();
          } catch (e2) {
            console.error("Failed to remove member", { groupId, membershipId, e2 });
            setMembersStatus("Remove failed.", true);
            setGlobalError(extractApiErrorMessage(e2));
          }
        }

        if (action === "member-save") {
          const select = membersResults.querySelector(
            `select[data-action="member-role"][data-membership-id="${membershipId}"]`
          );
          const role = select ? select.value : "reader";
          setMembersStatus("Saving…", false);
          try {
            const csrf = getCsrfToken();
            const headers = { Accept: "application/json", "Content-Type": "application/json" };
            if (csrf) headers["X-CSRFToken"] = csrf;

            await fetchJSONWithOptions(
              `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/${encodeURIComponent(String(membershipId))}/`,
              { method: "PATCH", headers, body: JSON.stringify({ role }) }
            );
            await refreshMembersFirstPage();
          } catch (e2) {
            console.error("Failed to update member role", { groupId, membershipId, e2 });
            setMembersStatus("Save failed.", true);
            setGlobalError(extractApiErrorMessage(e2));
          }
        }
      });
    }
  }

  function renderUsersList(payload) {
    const results = Array.isArray(payload && payload.results) ? payload.results : [];
    if (results.length === 0) return "";

    function renderUserGroups(groups) {
      if (!Array.isArray(groups) || groups.length === 0) return "";
      const pills = groups
        .map((g) => {
          const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
          const publicBadge = g.is_public_group ? " Public" : "";
          return `<a class="pill" href="${escapeHtml(href)}">${escapeHtml(g.name || g.slug || "")}${escapeHtml(publicBadge)}</a>`;
        })
        .join(" ");
      return `<div>${pills}</div>`;
    }

    return results
      .map((u) => {
        const id = u.id != null ? String(u.id) : "";
        const username = u.username || "";
        const email = u.email || "";
        const first = u.first_name || "";
        const last = u.last_name || "";
        const role = u.role || "";
        const isOwner = !!u.is_owner;
        const isActive = u.is_active !== false;
        const lastLogin = u.last_login ? String(u.last_login) : "";

        const badges = [
          isOwner ? '<span class="pill pill--owner">Owner</span>' : "",
          role ? `<span class="pill">${escapeHtml(role)}</span>` : "",
          isActive ? "" : '<span class="pill">inactive</span>',
        ]
          .filter(Boolean)
          .join(" ");

        const groupsHtml = renderUserGroups(u.groups);

        return `
          <article class="book">
            <h3 class="book__title">${escapeHtml(username)} ${badges}</h3>
            <div class="book__meta">
              ${email ? `<div>${escapeHtml(email)}</div>` : ""}
              ${(first || last) ? `<div>${escapeHtml([first, last].filter(Boolean).join(" "))}</div>` : ""}
              ${groupsHtml ? `<div>Groups: ${groupsHtml}</div>` : ""}
              ${lastLogin ? `<div>Last login: <span class="muted">${escapeHtml(lastLogin)}</span></div>` : ""}
            </div>
            <div style="margin-top: 10px;">
              <button class="button" type="button" data-action="edit-user" data-user-id="${escapeHtml(id)}">Edit</button>
            </div>
          </article>
        `.trim();
      })
      .join("");
  }

  function summarizeFieldErrors(body) {
    if (!body || typeof body !== "object") return "";
    const entries = Object.entries(body)
      .filter(([k]) => k !== "error" && k !== "detail")
      .slice(0, 8)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : String(v)}`);
    return entries.length ? entries.join(" | ") : "";
  }

  async function initUsers() {
    const me = await loadMeAndInitShell();
    setGlobalError("");

    const notAllowedEl = $("#users-not-allowed");
    const createLink = $("#users-create-link");
    const statusEl = $("#users-status");
    const resultsEl = $("#users-results");
    const nextBtn = $("#users-next");
    const prevBtn = $("#users-prev");

    const editStatus = $("#users-edit-status");
    const editForm = $("#users-edit-form");
    const editId = $("#users-edit-id");
    const editUsername = $("#users-edit-username");
    const editGroups = $("#users-edit-groups");
    const editEmail = $("#users-edit-email");
    const editFirst = $("#users-edit-first");
    const editLast = $("#users-edit-last");
    const editRole = $("#users-edit-role");
    const editActive = $("#users-edit-active");
    const saveStatus = $("#users-save-status");

    if (
      !notAllowedEl ||
      !statusEl ||
      !resultsEl ||
      !nextBtn ||
      !prevBtn ||
      !editStatus ||
      !editForm ||
      !editId ||
      !editUsername ||
      !editGroups ||
      !editEmail ||
      !editFirst ||
      !editLast ||
      !editRole ||
      !editActive ||
      !saveStatus
    ) {
      return;
    }

    const caps = me && me.capabilities ? me.capabilities : {};
    const allowed = !!caps.can_manage_users;

    visible(notAllowedEl, !allowed);
    visible(createLink, allowed);

    let nextUrl = null;
    let prevUrl = null;
    let currentUrl = "/api/v1/accounts/users/";
    let currentResults = [];

    function setStatus(text, isError) {
      statusEl.textContent = text;
      statusEl.classList.toggle("error", !!isError);
    }

    function setSaveStatus(text, isError) {
      saveStatus.textContent = text || "";
      saveStatus.classList.toggle("error", !!isError);
    }

    function setEditMessage(text, isError) {
      editStatus.textContent = text;
      editStatus.classList.toggle("error", !!isError);
    }

    function setFormEnabled(on, message) {
      const disabled = !on;
      editEmail.disabled = disabled;
      editFirst.disabled = disabled;
      editLast.disabled = disabled;
      editRole.disabled = disabled;
      editActive.disabled = disabled;
      const button = editForm.querySelector('button[type="submit"]');
      if (button) button.disabled = disabled;
      if (message) setEditMessage(message, true);
    }

    function applyRoleOptions() {
      const canSetManager = !!(me && me.is_owner);
      const mgrOpt = editRole.querySelector('option[value="manager"]');
      if (mgrOpt) mgrOpt.disabled = !canSetManager;
      if (!canSetManager && editRole.value === "manager") {
        editRole.value = "reader";
      }
    }

    function selectUser(user) {
      if (!user) return;

      editId.value = user.id != null ? String(user.id) : "";
      editUsername.textContent = user.username || "";
      if (Array.isArray(user.groups) && user.groups.length) {
        editGroups.innerHTML = user.groups
          .map((g) => {
            const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
            const badge = g.is_public_group ? ' <span class="pill pill--owner">Public</span>' : "";
            return `<div><a href="${escapeHtml(href)}">${escapeHtml(g.name || g.slug || "")}</a>${badge} <span class="muted">(${escapeHtml(g.membership_role || "")})</span></div>`;
          })
          .join("");
      } else {
        editGroups.innerHTML = '<div class="muted">No group memberships.</div>';
      }
      editEmail.value = user.email || "";
      editFirst.value = user.first_name || "";
      editLast.value = user.last_name || "";
      editRole.value = user.role || "reader";
      editActive.value = user.is_active === false ? "false" : "true";

      visible(editForm, true);
      setSaveStatus("", false);

      applyRoleOptions();

      if (user.is_owner) {
        setFormEnabled(false, "Owner cannot be edited here.");
      } else if (!me.is_owner && user.role === "manager") {
        setFormEnabled(false, "Only Owner can edit Managers.");
      } else {
        setFormEnabled(true, "");
        setEditMessage("Edit safe fields and save.", false);
      }
    }

    async function load(url) {
      setGlobalError("");
      setStatus("Loading users…", false);
      resultsEl.innerHTML = "";
      nextBtn.disabled = true;
      prevBtn.disabled = true;

      currentUrl = url;

      if (!allowed) {
        setStatus("Not allowed.", true);
        setEditMessage("Not allowed.", true);
        visible(editForm, false);
        return;
      }

      try {
        const payload = await fetchJSON(url);
        const results = Array.isArray(payload && payload.results) ? payload.results : [];
        currentResults = results;
        if (results.length === 0) {
          setStatus("No users.", false);
          nextUrl = null;
          prevUrl = null;
          return;
        }

        setStatus(payload && payload.count != null ? `Showing ${results.length} of ${payload.count}.` : "", false);
        resultsEl.innerHTML = renderUsersList(payload);

        nextUrl = payload.next || null;
        prevUrl = payload.previous || null;
        nextBtn.disabled = !nextUrl;
        prevBtn.disabled = !prevUrl;
      } catch (e) {
        console.error("Failed to load users", { url, e });
        setStatus("Error loading users.", true);
        setGlobalError(extractApiErrorMessage(e));
        nextUrl = null;
        prevUrl = null;
      }
    }

    await load(currentUrl);

    nextBtn.addEventListener("click", async () => {
      if (nextUrl) await load(nextUrl);
    });
    prevBtn.addEventListener("click", async () => {
      if (prevUrl) await load(prevUrl);
    });

    resultsEl.addEventListener("click", (e) => {
      const target = e.target;
      if (!target || target.nodeType !== 1) return;
      if (target.getAttribute("data-action") !== "edit-user") return;
      const id = target.getAttribute("data-user-id");
      if (!id) return;
      const user = (currentResults || []).find((u) => String(u.id) === String(id));
      selectUser(user);
    });

    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setSaveStatus("Saving…", false);
      setGlobalError("");

      const id = editId.value;
      if (!id) {
        setSaveStatus("No user selected.", true);
        return;
      }

      const selected = (currentResults || []).find((u) => String(u.id) === String(id));
      if (!selected) {
        setSaveStatus("Selected user not in current list; refresh.", true);
        return;
      }

      if (selected.is_owner) {
        setSaveStatus("Owner cannot be edited here.", true);
        return;
      }
      if (!me.is_owner && selected.role === "manager") {
        setSaveStatus("Only Owner can edit Managers.", true);
        return;
      }

      const desired = {
        email: editEmail.value || "",
        first_name: editFirst.value || "",
        last_name: editLast.value || "",
        role: editRole.value || "reader",
        is_active: editActive.value === "true",
      };

      const patch = {};
      for (const key of Object.keys(desired)) {
        if (String(desired[key]) !== String(selected[key])) {
          patch[key] = desired[key];
        }
      }

      if (Object.keys(patch).length === 0) {
        setSaveStatus("No changes.", false);
        return;
      }

      if (!me.is_owner && patch.role === "manager") {
        setSaveStatus("Only Owner can assign manager.", true);
        return;
      }

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        const updated = await fetchJSONWithOptions(`/api/v1/accounts/users/${encodeURIComponent(String(id))}/`, {
          method: "PATCH",
          headers,
          body: JSON.stringify(patch),
        });

        setSaveStatus("Saved.", false);
        await load(currentUrl);

        const updatedInList = (currentResults || []).find((u) => String(u.id) === String(id));
        selectUser(updatedInList || updated);
      } catch (e2) {
        console.error("Failed to save user", { id, e2 });
        const msg = extractApiErrorMessage(e2);
        const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
        setSaveStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
        setGlobalError(msg);
      }
    });
  }

  async function initUserNew() {
    const me = await loadMeAndInitShell();
    setGlobalError("");

    const notAllowedEl = $("#user-new-not-allowed");
    const statusEl = $("#user-new-status");
    const formCard = $("#user-new-form-card");
    const form = $("#user-new-form");
    const usernameInput = $("#user-new-username");
    const emailInput = $("#user-new-email");
    const firstInput = $("#user-new-first");
    const lastInput = $("#user-new-last");
    const roleSelect = $("#user-new-role");
    const activeInput = $("#user-new-active");
    const submitBtn = $("#user-new-submit");
    const submitStatus = $("#user-new-submit-status");

    const successCard = $("#user-new-success");
    const createdUsername = $("#user-new-created-username");
    const createdPassword = $("#user-new-created-password");

    if (
      !notAllowedEl ||
      !statusEl ||
      !formCard ||
      !form ||
      !usernameInput ||
      !emailInput ||
      !firstInput ||
      !lastInput ||
      !roleSelect ||
      !activeInput ||
      !submitBtn ||
      !submitStatus ||
      !successCard ||
      !createdUsername ||
      !createdPassword
    ) {
      return;
    }

    const caps = me && me.capabilities ? me.capabilities : {};
    const allowed = !!caps.can_manage_users;

    visible(notAllowedEl, !allowed);
    visible(formCard, allowed);

    if (!allowed) {
      statusEl.textContent = "Not allowed.";
      statusEl.classList.add("error");
      return;
    }

    statusEl.textContent = "";
    statusEl.classList.remove("error");

    const canCreateManager = !!(me && me.is_owner);
    const mgrOpt = roleSelect.querySelector('option[value="manager"]');
    if (mgrOpt) mgrOpt.disabled = !canCreateManager;
    if (!canCreateManager && roleSelect.value === "manager") {
      roleSelect.value = "reader";
    }

    function setSubmitStatus(text, isError) {
      submitStatus.textContent = text || "";
      submitStatus.classList.toggle("error", !!isError);
    }

    function setFormEnabled(on) {
      const disabled = !on;
      usernameInput.disabled = disabled;
      emailInput.disabled = disabled;
      firstInput.disabled = disabled;
      lastInput.disabled = disabled;
      roleSelect.disabled = disabled;
      activeInput.disabled = disabled;
      submitBtn.disabled = disabled;
    }

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      setGlobalError("");
      setSubmitStatus("Creating…", false);
      setFormEnabled(false);

      const payload = {
        username: (usernameInput.value || "").trim(),
        email: (emailInput.value || "").trim(),
        first_name: (firstInput.value || "").trim(),
        last_name: (lastInput.value || "").trim(),
        role: roleSelect.value || "reader",
        is_active: !!activeInput.checked,
      };

      if (!payload.username) {
        setSubmitStatus("Username is required.", true);
        setFormEnabled(true);
        return;
      }

      if (!canCreateManager && payload.role === "manager") {
        setSubmitStatus("Only Owner can create Managers.", true);
        setFormEnabled(true);
        return;
      }

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        const created = await fetchJSONWithOptions("/api/v1/accounts/users/", {
          method: "POST",
          headers,
          body: JSON.stringify(payload),
        });

        const u = created && created.user ? created.user : null;
        const pw = created && created.temporary_password ? String(created.temporary_password) : "";

        if (!u || !pw) {
          throw new Error("Unexpected response from server.");
        }

        createdUsername.textContent = u.username || payload.username;
        createdPassword.textContent = pw;

        visible(formCard, false);
        visible(successCard, true);
        setSubmitStatus("", false);
      } catch (e2) {
        console.error("Failed to create user", { e2 });
        const msg = extractApiErrorMessage(e2);
        const fieldMsg = summarizeFieldErrors(e2 && e2.body ? e2.body : null);
        setSubmitStatus(fieldMsg ? `${msg} (${fieldMsg})` : msg, true);
        setGlobalError(msg);
        setFormEnabled(true);
      }
    });
  }

  window.SecondPassUI = {
    initDashboard,
    initLibraryBrowse,
    initBookDetail,
    initImports,
    initGroupsList,
    initGroupDetail,
    initUsers,
    initUserNew,
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
    } else if (page === "users") {
      initUsers().catch((e) => {
        console.error("initUsers failed", e);
        setGlobalErrorFromError(e, "Users error:");
      });
    } else if (page === "user-new") {
      initUserNew().catch((e) => {
        console.error("initUserNew failed", e);
        setGlobalErrorFromError(e, "Create user error:");
      });
    } else {
      loadMeAndInitShell().catch((e) => {
        console.error("Shell init failed", e);
        setGlobalErrorFromError(e, "UI error:");
      });
    }
  });
})();
