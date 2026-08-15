import { ApiError } from "../errors";
import type { BookGroupAssignment, GroupMembership, LibraryGroup } from "./types";
import type { BookGroupAssignmentResponse, GroupMembershipResponse, LibraryGroupResponse } from "./wire";

export function mapLibraryGroup(response: LibraryGroupResponse): LibraryGroup {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    isPublicGroup: response.is_public_group,
    ...(response.preview_books === undefined ? {} : {
      previewBooks: response.preview_books.map(({ id, title, cover_url }) => ({ id, title, coverUrl: cover_url })),
    }),
  };
}

export function mapPreviewLimitError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields?.preview_limit) return error;
  const { preview_limit: previewLimit, ...fields } = error.fields;
  return new ApiError(error.message, error.status, { code: error.code, fields: { ...fields, previewLimit } });
}

export function mapGroupMembership(response: GroupMembershipResponse): GroupMembership {
  return { user: { profileId: response.user.profile_id, username: response.user.username }, isCurator: response.is_curator };
}

export function mapBookGroupAssignment(response: BookGroupAssignmentResponse): BookGroupAssignment {
  return { id: response.id, groupId: response.group_id, bookId: response.book_id };
}

export function mapBookAssignmentError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields) return error;
  const originalFields: Record<string, string[]> = error.fields;
  const messages = originalFields.book_id;
  if (!messages) return error;
  const fields: Record<string, string[]> = { ...originalFields, bookId: messages };
  delete fields.book_id;
  return new ApiError(error.message, error.status, { code: error.code, fields });
}

export function mapMembershipError(error: unknown): unknown {
  if (!(error instanceof ApiError) || !error.fields) return error;
  const aliases: Record<string, string> = { user_id: "userId", is_curator: "isCurator" };
  return new ApiError(error.message, error.status, {
    code: error.code,
    fields: Object.fromEntries(Object.entries(error.fields).map(([field, messages]) => [aliases[field] ?? field, messages])),
  });
}
