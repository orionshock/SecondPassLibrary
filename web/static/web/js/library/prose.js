import { escapeHtml } from "../layout.js";

function proseDomId(prefix, id) {
  const safeId = String(id || "unknown").replace(/[^A-Za-z0-9_-]/g, "-");
  return `library-${prefix}-prose-${safeId}`;
}

export function renderContextProseBlock({ text, idPrefix, itemId }) {
  const prose = text == null ? "" : String(text).trim();
  if (!prose) return "";

  const proseId = proseDomId(idPrefix, itemId);
  return `
    <div class="library-context__prose-wrap">
      <div id="${escapeHtml(proseId)}" class="library-context__prose" data-library-prose>${escapeHtml(prose)}</div>
      <button
        class="linklike library-context__prose-toggle"
        type="button"
        data-action="toggle-library-prose"
        data-target="${escapeHtml(proseId)}"
        aria-controls="${escapeHtml(proseId)}"
        aria-expanded="false"
      >Show More</button>
    </div>
  `.trim();
}

export function renderLibraryContext({
  filter,
  canEdit = false,
  editing = false,
  editName = null,
  editProse = null,
  status = "",
  error = "",
}) {
  const prose = filter && filter.prose != null ? String(filter.prose) : "";
  const proseLabel = filter && filter.proseLabel ? String(filter.proseLabel) : "Prose";
  const idPrefix = filter && filter.kind ? String(filter.kind) : "context";
  const itemId = filter && filter.id ? String(filter.id) : "";
  const name = filter && filter.name ? String(filter.name) : "";
  const label = filter && filter.label ? String(filter.label) : "Context";
  const message = status
    ? `<span class="library-context__status muted">${escapeHtml(status)}</span>`
    : "";
  const errorMessage = error
    ? `<span class="library-context__status error">${escapeHtml(error)}</span>`
    : "";

  if (editing) {
    const nameValue = editName != null ? String(editName) : name;
    const proseValue = editProse != null ? String(editProse) : prose;
    return `
      <div class="library-context">
        <div class="library-context__header">
          <span>${escapeHtml(label)}: <strong>${escapeHtml(name)}</strong></span>
          <button class="button" type="button" data-action="clear-library-filter">Clear</button>
        </div>
        <div class="library-context__editor">
          <label>
            <span>Name</span>
            <input type="text" name="library-context-name" value="${escapeHtml(nameValue)}" />
          </label>
          <label>
            <span>${escapeHtml(proseLabel)}</span>
            <textarea name="library-context-prose" rows="5">${escapeHtml(proseValue)}</textarea>
          </label>
          <div class="library-context__editor-actions">
            <button class="button" type="button" data-action="save-library-context">Save</button>
            <button class="button" type="button" data-action="cancel-library-context-edit">Cancel</button>
            ${message}
            ${errorMessage}
          </div>
        </div>
      </div>
    `.trim();
  }

  return `
    <div class="library-context">
      <div class="library-context__header">
        <span>${escapeHtml(label)}: <strong>${escapeHtml(name)}</strong></span>
        <span class="library-context__actions">
          ${canEdit ? '<button class="button" type="button" data-action="edit-library-context">Edit</button>' : ""}
          <button class="button" type="button" data-action="clear-library-filter">Clear</button>
        </span>
      </div>
      ${renderContextProseBlock({ text: prose, idPrefix, itemId })}
      ${message}
      ${errorMessage}
    </div>
  `.trim();
}

export function toggleProseBlock(button, root = document) {
  if (!(button instanceof HTMLElement)) return;
  const targetId = button.getAttribute("data-target") || "";
  const target = targetId ? root.querySelector(`#${CSS.escape(targetId)}`) : null;
  if (!(target instanceof HTMLElement)) return;

  const expanded = button.getAttribute("aria-expanded") === "true";
  const nextExpanded = !expanded;
  target.classList.toggle("is-expanded", nextExpanded);
  button.setAttribute("aria-expanded", nextExpanded ? "true" : "false");
  button.textContent = nextExpanded ? "Show Less" : "Show More";
}
