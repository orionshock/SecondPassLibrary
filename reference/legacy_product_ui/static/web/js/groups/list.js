import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { renderCoverPreviewStrip } from "../ui/cover_previews.js";
import { renderGroupBadge } from "../ui/groups.js";
import { createPagedListController } from "../ui/paged_list.js";
import { currentUserGroupMembership, truthy } from "./shared.js";

function renderGroupsList(payload, { me }) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((g) => {
      const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";
      const name = g.name ? String(g.name) : "Unknown group";
      const description = g.description ? String(g.description) : "";
      const descriptionSnippet =
        description && description.length > 160 ? `${description.slice(0, 160)}...` : description;

      const membership = currentUserGroupMembership({ me, group: g });
      const badgeBits = [
        membership && membership.is_curator === true ? '<span class="pill">Curator</span>' : "",
      ].filter(truthy);

      const badges = badgeBits.length ? `<span class="badge-row">${badgeBits.join(" ")}</span>` : "";
      const groupBadge = renderGroupBadge(g).outerHTML;
      const previews = renderCoverPreviewStrip(g.preview_books, {
        actionLabel: `View group ${name}`,
      });

      return `
        <article class="book group-list-card" data-group-url="${escapeHtml(href)}">
          <div class="group-list-card__main">
            <div class="identity-row">
              <h3 class="book__title identity-row__main group-list-card__title">
                <a href="${escapeHtml(href)}" title="Open group ${escapeHtml(name)}">${groupBadge}</a>
              </h3>
              ${badges}
            </div>
            ${descriptionSnippet ? `<div class="muted group-list-card__description">${escapeHtml(descriptionSnippet)}</div>` : ""}
          </div>
          ${previews}
        </article>
      `.trim();
    })
    .join("");
}

function isInteractiveElement(element) {
  return !!element.closest("a, button, input, select, textarea, label, summary, [role='button'], [role='link']");
}

function installGroupCardNavigation(root) {
  if (!root) return;
  root.addEventListener("click", (event) => {
    const source = event.target;
    if (!(source instanceof Element)) return;
    if (isInteractiveElement(source)) return;

    const card = source.closest("[data-group-url]");
    const url = card && card.getAttribute("data-group-url");
    if (url) window.location.assign(url);
  });
}

export async function initGroupsList() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const actionsEl = $("#groups-actions");
  if (actionsEl) {
    visible(actionsEl, !!(me && (me.is_owner || me.role === "manager")));
  }

  const statusEl = $("#groups-status");
  const resultsEl = $("#groups-results");
  const nextBtn = $("#groups-next");
  const prevBtn = $("#groups-prev");
  if (!statusEl || !resultsEl || !nextBtn || !prevBtn) return;

  installGroupCardNavigation(resultsEl);

  await createPagedListController({
    statusEl,
    resultsEl,
    nextBtn,
    prevBtn,
    initialUrl: "/api/v1/library/groups/?include_preview_books=true",
    emptyText: "No groups.",
    render: (payload) => renderGroupsList(payload, { me }),
  });
}
