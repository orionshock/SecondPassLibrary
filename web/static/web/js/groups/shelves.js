import { visible } from "../layout.js";
import { createGroupEditPager } from "./edit_pagination.js";
import { renderGroupShelvesCompact } from "./shared.js";

export async function initGroupShelvesTab({
  groupId,
  shelvesStatus,
  shelvesResults,
  shelvesNext,
  shelvesPrev,
  shelvesNote,
  shelvesActions,
  shelvesCreateLink,
  allowShelfManage,
}) {
  if (shelvesNote) {
    shelvesNote.textContent =
      "Shelves organize presentation and do not grant book access. Group shelves contain only books assigned to this group.";
  }

  visible(shelvesActions, !!allowShelfManage);
  if (allowShelfManage && shelvesCreateLink) {
    shelvesCreateLink.setAttribute(
      "href",
      `/shelves/new/?owner_group=${encodeURIComponent(String(groupId))}`
    );
  }

  if (shelvesStatus && shelvesResults && shelvesNext && shelvesPrev) {
    await createGroupEditPager({
      key: "shelves",
      tab: "shelves",
      statusEl: shelvesStatus,
      resultsEl: shelvesResults,
      nextBtn: shelvesNext,
      prevBtn: shelvesPrev,
      initialUrl: `/api/v1/shelves/?owner_group=${encodeURIComponent(String(groupId))}&include_preview_books=true`,
      emptyText: "No shelves yet.",
      render: (payload) => renderGroupShelvesCompact(payload, { canEdit: !!allowShelfManage }),
      loadErrorText: "Unable to load group shelves.",
    });
  }
}
