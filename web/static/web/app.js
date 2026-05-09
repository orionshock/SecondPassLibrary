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
            <h3 class="book__title">${escapeHtml(title)}${subtitle}</h3>
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

  window.SecondPassUI = {
    initDashboard,
    initLibraryBrowse,
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
    } else {
      loadMeAndInitShell().catch((e) => {
        console.error("Shell init failed", e);
        setGlobalErrorFromError(e, "UI error:");
      });
    }
  });
})();
