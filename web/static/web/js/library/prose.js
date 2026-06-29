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
