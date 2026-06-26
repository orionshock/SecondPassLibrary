import { extractApiErrorMessage, fetchJSON } from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import { createPagedListController } from "../ui/paged_list.js";
import { setStatus } from "../ui/status.js";
import { initTabs } from "../ui/tabs.js";
import { canEditGroupPage, renderBooksCompact, renderGroupShelvesCompact, renderMembersReadOnly } from "./shared.js";

export async function initGroupView() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#group-view-root");
  const summaryEl = $("#group-view-summary");
  const statusEl = $("#group-view-status");
  const titleEl = $("#group-view-title");
  const subtitleEl = $("#group-view-subtitle");
  const badgesEl = $("#group-view-badges");
  const descEl = $("#group-view-description");
  const editWrap = $("#group-view-edit-link-wrap");
  const editLink = $("#group-view-edit-link");

  const booksStatus = $("#group-view-books-status");
  const booksResults = $("#group-view-books-results");
  const booksNext = $("#group-view-books-next");
  const booksPrev = $("#group-view-books-prev");

  const membersNote = $("#group-view-members-note");
  const membersStatus = $("#group-view-members-status");
  const membersResults = $("#group-view-members-results");
  const membersNext = $("#group-view-members-next");
  const membersPrev = $("#group-view-members-prev");

  const shelvesStatus = $("#group-view-shelves-status");
  const shelvesResults = $("#group-view-shelves-results");
  const shelvesNext = $("#group-view-shelves-next");
  const shelvesPrev = $("#group-view-shelves-prev");

  if (
    !root ||
    !summaryEl ||
    !statusEl ||
    !titleEl ||
    !subtitleEl ||
    !badgesEl ||
    !descEl ||
    !booksStatus ||
    !booksResults ||
    !booksNext ||
    !booksPrev ||
    !membersStatus ||
    !membersResults ||
    !membersNext ||
    !membersPrev ||
    !membersNote
  ) {
    return;
  }

  initTabs(root);

  const groupId = root.getAttribute("data-group-id") || "";
  if (!groupId) return;

  setStatus(statusEl, "Loading...", false);
  visible(root, false);
  visible(summaryEl, false);
  visible(editWrap, false);

  let group = null;
  try {
    group = await fetchJSON(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`);
  } catch (e) {
    console.error("Failed to load group", { groupId, e });
    if (e && e.status === 404) setStatus(statusEl, "Not found or not accessible.", true);
    else if (e && e.status === 403) setStatus(statusEl, "Permission denied.", true);
    else setStatus(statusEl, "Error loading group.", true);
    setGlobalError(extractApiErrorMessage(e));
    return;
  }

  const isPublicGroup = !!group.is_public_group;
  titleEl.textContent = group.name || "Group";

  subtitleEl.textContent = "";

  if (canEditGroupPage({ me, group })) {
    if (editLink) editLink.setAttribute("href", `/groups/${encodeURIComponent(String(groupId))}/edit/`);
    visible(editWrap, true);
  }

  // Stable details card above tabs.
  badgesEl.textContent = "";
  const badgesNode = document.createElement("div");
  if (isPublicGroup) {
    const b = document.createElement("span");
    b.className = "pill pill--owner";
    b.textContent = "Public";
    badgesNode.appendChild(b);
  }
  if (group.is_curator) {
    if (badgesNode.childNodes.length) badgesNode.appendChild(document.createTextNode(" "));
    const b2 = document.createElement("span");
    b2.className = "pill";
    b2.textContent = "Curator";
    badgesNode.appendChild(b2);
  }
  badgesEl.appendChild(badgesNode);
  descEl.textContent = group.description || "";

  visible(summaryEl, true);
  visible(root, true);
  setStatus(statusEl, "", false);

  await createPagedListController({
    statusEl: booksStatus,
    resultsEl: booksResults,
    nextBtn: booksNext,
    prevBtn: booksPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/books/`,
    emptyText: "No books in this group.",
    render: (payload) => renderBooksCompact(payload, { groupId, canRemove: false }),
  });

  membersNote.textContent = "";
  await createPagedListController({
    statusEl: membersStatus,
    resultsEl: membersResults,
    nextBtn: membersNext,
    prevBtn: membersPrev,
    initialUrl: `/api/v1/library/groups/${encodeURIComponent(String(groupId))}/memberships/`,
    emptyText: "No members.",
    render: (payload) => renderMembersReadOnly(payload),
  });

  if (shelvesStatus && shelvesResults && shelvesNext && shelvesPrev) {
    await createPagedListController({
      statusEl: shelvesStatus,
      resultsEl: shelvesResults,
      nextBtn: shelvesNext,
      prevBtn: shelvesPrev,
      initialUrl: `/api/v1/shelves/?owner_group=${encodeURIComponent(String(groupId))}`,
      emptyText: "No shelves yet.",
      render: (payload) => renderGroupShelvesCompact(payload, { canEdit: false }),
    });
  }
}
