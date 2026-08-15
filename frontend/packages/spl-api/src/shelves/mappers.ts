import { ApiError } from "../errors";
import { mapCompactBook } from "../library/compactBooks";
import type { ShelfEditorItem, ShelfItem, ShelfOwnerUser, ShelfSummary } from "./types";
import type { ShelfEditorItemResponse, ShelfItemResponse, ShelfOwnerUserResponse, ShelfSummaryResponse } from "./wire";

export function mapShelfSummary(response: ShelfSummaryResponse): ShelfSummary {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    ownerType: response.owner_type,
    ownerUser: response.owner_user ? { profileId: response.owner_user.profile_id, username: response.owner_user.username } : null,
    ownerGroup: response.owner_group ? { id: response.owner_group.id, name: response.owner_group.name, isPublicGroup: response.owner_group.is_public_group } : null,
    visibility: response.visibility,
    itemCount: response.item_count,
    ...(response.matched_item_id !== undefined ? { matchedItemId: response.matched_item_id } : {}),
    canEdit: response.can_edit,
    ...(response.preview_books === undefined ? {} : { previewBooks: response.preview_books.map(({ id, title, cover_url }) => ({ id, title, coverUrl: cover_url })) }),
  };
}

export function mapPreviewLimitError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields?.preview_limit) return error;
  const { preview_limit: previewLimit, ...fields } = error.fields;
  return new ApiError(error.message, error.status, { code: error.code, fields: { ...fields, previewLimit } });
}

export function mapShelfItem(response: ShelfItemResponse): ShelfItem {
  return { id: response.id, shelfId: response.shelf, book: mapCompactBook(response.book), position: response.position, addedBy: mapShelfOwnerUser(response.added_by) };
}

export function mapShelfEditorItem(response: ShelfEditorItemResponse): ShelfEditorItem {
  const addedBy = mapShelfOwnerUser(response.added_by);
  if (response.unavailable || response.book === null) {
    return { id: response.id, shelfId: response.shelf, position: response.position, unavailable: true, book: null, addedBy };
  }
  return { id: response.id, shelfId: response.shelf, position: response.position, unavailable: false, book: mapCompactBook(response.book), addedBy };
}

export function mapVisibleShelfEditorItem(response: ShelfItemResponse): ShelfEditorItem {
  return { ...mapShelfItem(response), unavailable: false };
}

function mapShelfOwnerUser(response: ShelfOwnerUserResponse | null): ShelfOwnerUser | null {
  return response ? { profileId: response.profile_id, username: response.username } : null;
}
