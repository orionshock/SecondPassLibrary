import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { renderGroupBadge } from "../ui/groups.js";
import { createPagedListController } from "../ui/paged_list.js";
import { truthy } from "./shared.js";

function renderGroupsList(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((g) => {
      const membershipRole = g.membership_role || "";
      const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";

      const badgeBits = [
        membershipRole ? `<span class="pill">Your role: ${escapeHtml(membershipRole)}</span>` : "",
      ].filter(truthy);

      const badges = badgeBits.length ? `<span class="badge-row">${badgeBits.join(" ")}</span>` : "";
      const groupBadge = renderGroupBadge(g).outerHTML;

      return `
        <article class="book card-row--compact">
          <div class="identity-row">
            <h3 class="book__title identity-row__main">
              <a href="${escapeHtml(href)}">${groupBadge}</a>
            </h3>
            ${badges}
          </div>
        </article>
      `.trim();
    })
    .join("");
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

  await createPagedListController({
    statusEl,
    resultsEl,
    nextBtn,
    prevBtn,
    initialUrl: "/api/v1/library/groups/",
    emptyText: "No groups.",
    render: renderGroupsList,
  });
}
