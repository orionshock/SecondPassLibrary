import {
  extractApiErrorMessage,
  fetchAllPaginatedResults,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { canManageLibrary } from "../auth.js";
import { $, loadMeAndInitShell, visible } from "../layout.js";
import { setStatus } from "../ui/status.js";

function config(root) {
  return {
    kind: String(root.dataset.kind || ""),
    label: String(root.dataset.label || "Catalog entity"),
    id: String(root.dataset.entityId || ""),
  };
}

function apiBase(kind) {
  return `/api/v1/library/${encodeURIComponent(kind)}/`;
}

function managementApiUrl(kind, id = "") {
  const url = new URL(`${apiBase(kind)}${id ? `${encodeURIComponent(id)}/` : ""}`, window.location.origin);
  url.searchParams.set("management", "true");
  return url.toString();
}

function normalizeName(value) {
  return String(value || "").normalize("NFKC").trim().replace(/\s+/g, " ").toLocaleLowerCase();
}

function safeError(error, fallback) {
  return String(extractApiErrorMessage(error) || fallback).slice(0, 240);
}

function renderEntityRow(entity, { kind, label }) {
  const row = document.createElement("article");
  row.className = "catalog-management-row";
  const main = document.createElement("div");
  const link = document.createElement("a");
  link.href = `/library/${kind}/${encodeURIComponent(String(entity.id))}/`;
  link.textContent = String(entity.name || `Untitled ${label}`);
  link.className = "catalog-management-row__title";
  main.appendChild(link);
  const meta = document.createElement("div");
  meta.className = "muted";
  meta.textContent = `${Number(entity.book_count || 0)} Books · Sort: ${String(entity.sort_name || entity.name || "")}`;
  main.appendChild(meta);
  const edit = document.createElement("a");
  edit.className = "button button--secondary";
  edit.href = `/library/${kind}/${encodeURIComponent(String(entity.id))}/edit/`;
  edit.textContent = "Edit";
  row.append(main, edit);
  return row;
}

function renderBookRow(book) {
  const row = document.createElement("div");
  row.className = "catalog-management-row";
  const link = document.createElement("a");
  link.href = `/library/books/${encodeURIComponent(String(book.id))}/`;
  link.textContent = String(book.title || "Untitled book");
  row.appendChild(link);
  return row;
}

async function requireManager() {
  const me = await loadMeAndInitShell();
  if (!canManageLibrary(me)) throw new Error("Not allowed.");
}

export async function initCatalogEntityList() {
  await requireManager();
  const root = $("#catalog-entity-list");
  if (!root) return;
  const cfg = config(root);
  const form = $("#catalog-entity-search");
  const input = $("#catalog-entity-q");
  const status = $("#catalog-entity-status");
  const results = $("#catalog-entity-results");
  const previous = $("#catalog-entity-prev");
  const next = $("#catalog-entity-next");
  const range = $("#catalog-entity-range");
  if (!form || !input || !status || !results || !previous || !next || !range) return;
  let page = 1;
  let hasNext = false;
  let hasPrevious = false;

  async function load() {
    const url = new URL(managementApiUrl(cfg.kind));
    const query = input.value.trim();
    if (query) url.searchParams.set("q", query);
    url.searchParams.set("page", String(page));
    setStatus(status, "Loading...", false);
    results.replaceChildren();
    try {
      const payload = await fetchJSON(url.toString());
      const rows = Array.isArray(payload.results) ? payload.results : [];
      for (const entity of rows) results.appendChild(renderEntityRow(entity, cfg));
      hasNext = !!payload.next;
      hasPrevious = !!payload.previous;
      previous.disabled = !hasPrevious;
      next.disabled = !hasNext;
      range.textContent = `${Number(payload.count || rows.length)} ${cfg.label}s`;
      setStatus(status, rows.length ? "" : `No ${cfg.label.toLowerCase()}s.`, false);
    } catch (error) {
      setStatus(status, safeError(error, `Failed to load ${cfg.label.toLowerCase()}s.`), true);
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    page = 1;
    load();
  });
  previous.addEventListener("click", () => { if (hasPrevious) { page -= 1; load(); } });
  next.addEventListener("click", () => { if (hasNext) { page += 1; load(); } });
  await load();
}

async function loadAttachedBooks(cfg) {
  const url = new URL("/api/v1/library/books/", window.location.origin);
  url.searchParams.set(cfg.kind === "authors" ? "author" : "series", cfg.id);
  url.searchParams.set("page_size", "100");
  if (cfg.kind === "series") url.searchParams.set("ordering", "series_index");
  const payload = await fetchJSON(url.toString());
  return Array.isArray(payload.results) ? payload.results : [];
}

export async function initCatalogEntityDetail() {
  await requireManager();
  const root = $("#catalog-entity-detail");
  if (!root) return;
  const cfg = config(root);
  const status = $("#catalog-entity-status");
  const content = $("#catalog-entity-detail-content");
  const name = $("#catalog-entity-name");
  const sortName = $("#catalog-entity-sort-name");
  const prose = $("#catalog-entity-prose");
  const books = $("#catalog-entity-books");
  if (!status || !content || !name || !sortName || !prose || !books) return;
  try {
    const [entity, attached] = await Promise.all([
      fetchJSON(managementApiUrl(cfg.kind, cfg.id)),
      loadAttachedBooks(cfg),
    ]);
    name.textContent = String(entity.name || cfg.label);
    sortName.textContent = String(entity.sort_name || entity.name || "");
    prose.textContent = String(cfg.kind === "authors" ? entity.biography || "" : entity.summary || "");
    for (const book of attached) books.appendChild(renderBookRow(book));
    if (!attached.length) books.textContent = "No attached Books.";
    visible(content, true);
    setStatus(status, "", false);
  } catch (error) {
    setStatus(status, safeError(error, `Failed to load ${cfg.label.toLowerCase()}.`), true);
  }
}

export async function initCatalogEntityForm() {
  await requireManager();
  const root = $("#catalog-entity-form-root");
  if (!root) return;
  const cfg = config(root);
  const form = $("#catalog-entity-form");
  const name = $("#catalog-entity-name");
  const sortName = $("#catalog-entity-sort-name");
  const prose = $("#catalog-entity-prose");
  const warning = $("#catalog-entity-duplicate-warning");
  const formStatus = $("#catalog-entity-form-status");
  const attachedRoot = $("#catalog-entity-attached-books");
  const deleteButton = $("#catalog-entity-delete-btn");
  const deleteHelp = $("#catalog-entity-delete-help");
  const deleteStatus = $("#catalog-entity-delete-status");
  if (!form || !name || !sortName || !prose || !warning || !formStatus) return;
  let allEntities = [];
  let attached = [];

  function updateDuplicateWarning() {
    const normalized = normalizeName(name.value);
    const matches = allEntities.filter(
      (entity) => String(entity.id) !== cfg.id && normalizeName(entity.name) === normalized
    );
    warning.textContent = matches.length
      ? `${matches.length} other ${cfg.label.toLowerCase()} record${matches.length === 1 ? "" : "s"} share this normalized name.`
      : "";
    visible(warning, matches.length > 0);
  }

  try {
    allEntities = await fetchAllPaginatedResults(managementApiUrl(cfg.kind));
    if (cfg.id) {
      const [entity, books] = await Promise.all([
        fetchJSON(managementApiUrl(cfg.kind, cfg.id)),
        loadAttachedBooks(cfg),
      ]);
      name.value = String(entity.name || "");
      sortName.value = String(entity.sort_name || "");
      prose.value = String(cfg.kind === "authors" ? entity.biography || "" : entity.summary || "");
      attached = books;
      if (attachedRoot) {
        for (const book of attached) attachedRoot.appendChild(renderBookRow(book));
        if (!attached.length) attachedRoot.textContent = "No attached Books.";
      }
      if (deleteButton) deleteButton.disabled = attached.length > 0;
      if (deleteHelp && attached.length) {
        deleteHelp.textContent = `${cfg.label} cannot be deleted while attached to Books.`;
      }
    }
    updateDuplicateWarning();
  } catch (error) {
    setStatus($("#catalog-entity-load-status"), safeError(error, "Failed to load form."), true);
  }

  name.addEventListener("input", updateDuplicateWarning);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const payload = {
      name: name.value.trim(),
      sort_name: sortName.value.trim(),
      [cfg.kind === "authors" ? "biography" : "summary"]: prose.value.trim(),
    };
    const csrf = getCsrfToken();
    try {
      const entity = await fetchJSONWithOptions(
        cfg.id ? `${apiBase(cfg.kind)}${encodeURIComponent(cfg.id)}/` : apiBase(cfg.kind),
        {
          method: cfg.id ? "PATCH" : "POST",
          headers: { Accept: "application/json", "Content-Type": "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
          body: JSON.stringify(payload),
        }
      );
      window.location.assign(`/library/${cfg.kind}/${encodeURIComponent(String(entity.id))}/`);
    } catch (error) {
      setStatus(formStatus, safeError(error, `${cfg.label} could not be saved.`), true);
    }
  });

  if (deleteButton && deleteStatus) {
    deleteButton.addEventListener("click", async () => {
      if (attached.length || !window.confirm(`Delete this ${cfg.label.toLowerCase()}?`)) return;
      const csrf = getCsrfToken();
      try {
        await fetchJSONWithOptions(`${apiBase(cfg.kind)}${encodeURIComponent(cfg.id)}/`, {
          method: "DELETE",
          headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
        });
        window.location.assign(`/library/${cfg.kind}/`);
      } catch (error) {
        setStatus(deleteStatus, safeError(error, `${cfg.label} could not be deleted.`), true);
      }
    });
  }
}
