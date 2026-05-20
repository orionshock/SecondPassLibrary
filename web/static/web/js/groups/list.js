import { $, escapeHtml, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { pagedListController, truthy } from "./shared.js";

function renderGroupsList(payload) {
  const results = Array.isArray(payload && payload.results) ? payload.results : [];
  if (results.length === 0) return "";

  return results
    .map((g) => {
      const name = g.name || "";
      const membershipRole = g.membership_role || "";
      const isPublic = !!g.is_public_group;
      const href = g.id ? `/groups/${encodeURIComponent(String(g.id))}/` : "#";

      const badgeBits = [
        isPublic ? '<span class="pill pill--owner">Public</span>' : "",
        membershipRole ? `<span class="pill">Your role: ${escapeHtml(membershipRole)}</span>` : "",
      ].filter(truthy);

      const badges = badgeBits.length ? `<span class="edit-header__badges">${badgeBits.join(" ")}</span>` : "";

      return `
        <article class="book">
          <div style="display:flex; gap: 12px; justify-content: space-between; align-items: baseline; flex-wrap: wrap;">
            <div>
              <h3 class="book__title" style="display:inline;">
                <a href="${escapeHtml(href)}">${escapeHtml(name)}</a>
              </h3>
              ${badges ? ` <span style="margin-left: 8px;">${badges}</span>` : ""}
            </div>
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

  await pagedListController({
    statusEl,
    resultsEl,
    nextBtn,
    prevBtn,
    initialUrl: "/api/v1/library/groups/",
    emptyText: "No groups.",
    render: renderGroupsList,
  });
}
