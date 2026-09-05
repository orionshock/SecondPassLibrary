import type { BookOrdering, BookPreview, LibrarySearchOrdering } from "../library";

export interface LibraryGroup {
  id: string;
  name: string;
  description: string;
  isPublicGroup: boolean;
  previewBooks?: BookPreview[];
}

export interface BookGroupAssignment { id: string; groupId: string; bookId: string; }

export interface LibraryGroupsQuery {
  q?: string;
  bookId?: string;
  ordering?: "name" | "-name";
  includePreviewBooks?: boolean;
  previewLimit?: number;
  page?: number;
  pageSize?: number;
}

export interface CreateGroupInput { name: string; description: string; }
export interface UpdateGroupInput { name?: string; description?: string; }

export interface GroupBooksQuery {
  q?: string;
  tag?: string;
  authorId?: string;
  seriesId?: string;
  publisher?: string;
  excludeShelfId?: string;
  ordering?: BookOrdering;
  page?: number;
  pageSize?: number;
}

export interface GroupBookSearchQuery {
  q: string;
  tag?: string;
  excludeShelfId?: string;
  ordering?: LibrarySearchOrdering;
  page?: number;
  pageSize?: number;
}

export interface GroupMembersQuery { page?: number; pageSize?: number; }
export interface GroupMembership { user: { profileId: string; username: string }; isCurator: boolean; }
export interface AddGroupMemberInput { userId: string; isCurator: boolean; }
export interface UpdateGroupMemberInput { isCurator: boolean; }
