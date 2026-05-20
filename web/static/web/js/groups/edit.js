import {
  extractApiErrorMessage,
  fetchJSON,
  fetchJSONWithOptions,
  getCsrfToken,
} from "../api.js";
import { $, loadMeAndInitShell, setGlobalError, visible } from "../layout.js";
import {
  canEditGroupDescription,
  canEditGroupPage,
  canManageGroupBooks,
  isManagerOrOwner,
  initTabs,
  setStatus,
} from "./shared.js";
import { initGroupBooksTab } from "./books.js";
import { initGroupMembershipsTab } from "./memberships.js";
import { initGroupShelvesTab } from "./shelves.js";

export async function initGroupEdit() {
  const me = await loadMeAndInitShell();
  setGlobalError("");

  const root = $("#group-edit-root");
  const summaryEl = $("#group-edit-summary");
  const statusEl = $("#group-edit-status");
  const titleEl = $("#group-edit-title");
  const subtitleEl = $("#group-edit-subtitle");
  const notAllowedEl = $("#group-edit-not-allowed");

  const badgesEl = $("#group-edit-badges");
  const descPreviewEl = $("#group-edit-description-preview");
  const editForm = $("#group-edit-form");
  const descInput = $("#group-edit-description");
  const saveStatus = $("#group-edit-save-status");

  const bookSearchForm = $("#group-edit-book-search-form");
  const bookSearchInput = $("#group-edit-book-search");
  const bookSearchStatus = $("#group-edit-book-search-status");
  const bookSearchWrap = $("#group-edit-book-search-results-wrap");
  const bookSearchResults = $("#group-edit-book-search-results");
  const bookSearchPrev = $("#group-edit-book-search-prev");
  const bookSearchNext = $("#group-edit-book-search-next");

  const uuidDebugDetails = $("#group-edit-book-uuid-debug");
  const addBookForm = $("#group-edit-add-book");
  const addBookInput = $("#group-edit-book-id");
  const addBookStatus = $("#group-edit-add-book-status");
  const booksStatus = $("#group-edit-books-status");
  const booksResults = $("#group-edit-books-results");
  const booksNext = $("#group-edit-books-next");
  const booksPrev = $("#group-edit-books-prev");

  const membersNote = $("#group-edit-members-note");
  const addMemberForm = $("#group-edit-add-member");
  const addMemberUser = $("#group-edit-member-user");
  const addMemberRole = $("#group-edit-member-role");
  const addMemberStatus = $("#group-edit-add-member-status");
  const membersStatus = $("#group-edit-members-status");
  const membersResults = $("#group-edit-members-results");
  const membersNext = $("#group-edit-members-next");
  const membersPrev = $("#group-edit-members-prev");

  const shelvesNote = $("#group-edit-shelves-note");
  const shelvesActions = $("#group-edit-shelves-actions");
  const shelvesCreateLink = $("#group-edit-shelves-create-link");
  const shelvesStatus = $("#group-edit-shelves-status");
  const shelvesResults = $("#group-edit-shelves-results");
  const shelvesNext = $("#group-edit-shelves-next");
  const shelvesPrev = $("#group-edit-shelves-prev");

  const deleteRoot = $("#group-delete-root");
  const deleteForm = $("#group-delete-form");
  const deleteConfirm = $("#group-delete-confirm");
  const deleteBtn = $("#group-delete-btn");
  const deleteStatus = $("#group-delete-status");

  if (
    !root ||
    !summaryEl ||
    !statusEl ||
    !titleEl ||
    !subtitleEl ||
    !notAllowedEl ||
    !badgesEl ||
    !descPreviewEl ||
    !editForm ||
    !descInput ||
    !saveStatus ||
    !bookSearchForm ||
    !bookSearchInput ||
    !bookSearchStatus ||
    !bookSearchWrap ||
    !bookSearchResults ||
    !bookSearchPrev ||
    !bookSearchNext ||
    !uuidDebugDetails ||
    !addBookForm ||
    !addBookInput ||
    !addBookStatus ||
    !booksStatus ||
    !booksResults ||
    !booksNext ||
    !booksPrev ||
    !membersNote ||
    !addMemberForm ||
    !addMemberUser ||
    !addMemberRole ||
    !addMemberStatus ||
    !membersStatus ||
    !membersResults ||
    !membersNext ||
    !membersPrev
  ) {
    return;
  }

  initTabs(root);

  const groupId = root.getAttribute("data-group-id") || "";
  if (!groupId) return;

  setStatus(statusEl, "Loadingâ€¦", false);
  visible(root, false);
  visible(summaryEl, false);
  visible(notAllowedEl, false);

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

  if (!canEditGroupPage({ me, group })) {
    setStatus(statusEl, "", false);
    visible(notAllowedEl, true);
    visible(root, false);
    visible(summaryEl, false);
    return;
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
  if (group.membership_role) {
    if (badgesNode.childNodes.length) badgesNode.appendChild(document.createTextNode(" "));
    const b2 = document.createElement("span");
    b2.className = "pill";
    b2.textContent = `Your role: ${group.membership_role}`;
    badgesNode.appendChild(b2);
  }
  badgesEl.appendChild(badgesNode);
  descPreviewEl.textContent = group.description || "";

  visible(summaryEl, true);
  visible(root, true);
  setStatus(statusEl, "", false);

  const allowDescriptionEdit = canEditGroupDescription({ me, group });
  descInput.value = group.description || "";
  visible(editForm, allowDescriptionEdit);

  // Delete (Owner/Manager only; never for Public)
  if (deleteRoot && deleteForm && deleteConfirm && deleteBtn && deleteStatus) {
    const allowDelete = isManagerOrOwner(me) && !isPublicGroup;
    visible(deleteRoot, allowDelete);
    deleteConfirm.value = "";
    deleteBtn.disabled = true;
    deleteStatus.textContent = "";

    function syncDeleteEnabled() {
      const typed = String(deleteConfirm.value || "").trim();
      deleteBtn.disabled = typed !== String(group.name || "").trim();
    }
    deleteConfirm.addEventListener("input", syncDeleteEnabled);

    deleteForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (deleteBtn.disabled) return;
      deleteStatus.textContent = "Deleting…";
      deleteStatus.classList.remove("error");
      setGlobalError("");

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`, {
          method: "DELETE",
          headers,
        });
        window.location.href = "/groups/";
      } catch (e2) {
        console.error("Failed to delete group", { groupId, e2 });
        const msg = extractApiErrorMessage(e2) || "Failed to delete group.";
        deleteStatus.textContent = msg;
        deleteStatus.classList.add("error");
        setGlobalError(msg);
      }
    });
  } else if (deleteRoot) {
    visible(deleteRoot, false);
  }

  function setSaveStatus(text, isError) {
    setStatus(saveStatus, text, isError);
  }

  if (allowDescriptionEdit) {
    editForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      setSaveStatus("Savingâ€¦", false);
      setGlobalError("");

      try {
        const csrf = getCsrfToken();
        const headers = { Accept: "application/json", "Content-Type": "application/json" };
        if (csrf) headers["X-CSRFToken"] = csrf;

        await fetchJSONWithOptions(`/api/v1/library/groups/${encodeURIComponent(String(groupId))}/`, {
          method: "PATCH",
          headers,
          body: JSON.stringify({ description: descInput.value || "" }),
        });
        setSaveStatus("Saved.", false);
      } catch (e2) {
        console.error("Failed to save group description", { groupId, e2 });
        setSaveStatus(extractApiErrorMessage(e2), true);
        setGlobalError(extractApiErrorMessage(e2));
      }
    });
  }

  const allowBookManage = canManageGroupBooks({ me, group });
  await initGroupBooksTab({
    me,
    groupId,
    allowBookManage,
    bookSearchForm,
    bookSearchInput,
    bookSearchStatus,
    bookSearchWrap,
    bookSearchResults,
    bookSearchPrev,
    bookSearchNext,
    uuidDebugDetails,
    addBookForm,
    addBookInput,
    addBookStatus,
    booksStatus,
    booksResults,
    booksNext,
    booksPrev,
  });

  await initGroupMembershipsTab({
    me,
    groupId,
    isPublicGroup,
    membersNote,
    addMemberForm,
    addMemberUser,
    addMemberRole,
    addMemberStatus,
    membersStatus,
    membersResults,
    membersNext,
    membersPrev,
  });

  const allowShelfManage = canManageGroupBooks({ me, group });
  await initGroupShelvesTab({
    groupId,
    shelvesStatus,
    shelvesResults,
    shelvesNext,
    shelvesPrev,
    shelvesNote,
    shelvesActions,
    shelvesCreateLink,
    allowShelfManage,
  });
}
