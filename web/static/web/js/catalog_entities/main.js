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
import { productUiPath } from "../ui/paths.js";

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

function renderBookRow(book) {
  const row = document.createElement("a");
  row.className = "catalog-entity-book-preview";
  row.href = productUiPath(`/library/books/${encodeURIComponent(String(book.id))}/`);
  const cover = document.createElement("span");
  cover.className = "catalog-entity-book-preview__cover";
  const coverUrl = String(book.cover_url || "");
  if (coverUrl) {
    const image = document.createElement("img");
    image.src = coverUrl;
    image.alt = "";
    image.loading = "lazy";
    cover.appendChild(image);
  } else {
    cover.textContent = "Cover";
    cover.setAttribute("aria-hidden", "true");
  }
  const title = document.createElement("span");
  title.className = "catalog-entity-book-preview__title";
  title.textContent = String(book.title || "Untitled book");
  row.append(cover, title);
  return row;
}

async function requireManager() {
  const me = await loadMeAndInitShell();
  if (!canManageLibrary(me)) throw new Error("Not allowed.");
}

async function loadAttachedBooks(cfg) {
  const url = new URL("/api/v1/library/books/", window.location.origin);
  url.searchParams.set(cfg.kind === "authors" ? "author" : "series", cfg.id);
  url.searchParams.set("page_size", "100");
  if (cfg.kind === "series") url.searchParams.set("ordering", "series_index");
  const payload = await fetchJSON(url.toString());
  const books = Array.isArray(payload.results) ? payload.results : [];
  return { books, count: Number(payload.count || books.length) };
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
  const deleteForm = $("#catalog-entity-delete-form");
  const deleteConfirmFields = $("#catalog-entity-delete-confirm-fields");
  const deleteConfirm = $("#catalog-entity-delete-confirm");
  const deleteButton = $("#catalog-entity-delete-btn");
  const deleteHelp = $("#catalog-entity-delete-help");
  const deleteStatus = $("#catalog-entity-delete-status");
  if (!form || !name || !sortName || !prose || !warning || !formStatus) return;
  let allEntities = [];
  let attached = [];
  let attachedCount = 0;
  let entityName = "";

  function syncDeleteEnabled() {
    if (!deleteButton || !deleteConfirm) return;
    deleteButton.disabled = attachedCount > 0 || deleteConfirm.value !== entityName;
  }

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
      const [entity, attachedPayload] = await Promise.all([
        fetchJSON(managementApiUrl(cfg.kind, cfg.id)),
        loadAttachedBooks(cfg),
      ]);
      entityName = String(entity.name || "");
      name.value = entityName;
      sortName.value = String(entity.sort_name || "");
      prose.value = String(cfg.kind === "authors" ? entity.biography || "" : entity.summary || "");
      attached = attachedPayload.books;
      attachedCount = attachedPayload.count;
      if (attachedRoot) {
        for (const book of attached) attachedRoot.appendChild(renderBookRow(book));
        if (!attached.length) attachedRoot.textContent = "No attached Books.";
      }
      if (deleteConfirm) {
        deleteConfirm.value = "";
        deleteConfirm.disabled = attachedCount > 0;
      }
      if (deleteConfirmFields) visible(deleteConfirmFields, attachedCount === 0);
      if (deleteHelp) {
        deleteHelp.textContent = attachedCount
          ? `${cfg.label} cannot be deleted because ${attachedCount} ${attachedCount === 1 ? "book is" : "books are"} attached.`
          : `No books are attached. Type the ${cfg.label.toLowerCase()} name to enable deletion.`;
      }
      syncDeleteEnabled();
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
      const singular = cfg.kind === "authors" ? "author" : "series";
      window.location.assign(productUiPath(`/library/?view=${singular}&${singular}=${encodeURIComponent(String(entity.id))}`));
    } catch (error) {
      setStatus(formStatus, safeError(error, `${cfg.label} could not be saved.`), true);
    }
  });

  if (deleteForm && deleteConfirm && deleteButton && deleteStatus) {
    deleteConfirm.addEventListener("input", syncDeleteEnabled);
    deleteForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      if (deleteButton.disabled || attachedCount > 0) return;
      if (!window.confirm(`Permanently delete ${entityName || `this ${cfg.label.toLowerCase()}`}? This cannot be undone.`)) return;
      const csrf = getCsrfToken();
      try {
        await fetchJSONWithOptions(`${apiBase(cfg.kind)}${encodeURIComponent(cfg.id)}/`, {
          method: "DELETE",
          headers: { Accept: "application/json", ...(csrf ? { "X-CSRFToken": csrf } : {}) },
        });
        window.location.assign(productUiPath(`/library/?view=${cfg.kind}`));
      } catch (error) {
        setStatus(deleteStatus, safeError(error, `${cfg.label} could not be deleted.`), true);
      }
    });
  }
}
