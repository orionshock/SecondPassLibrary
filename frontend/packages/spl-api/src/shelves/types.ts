import type { BookPreview, CompactBook } from "../library";
import type { Page } from "../pagination";

export type ShelfOwnerType = "user" | "group";
export type ShelfVisibility = "private" | "listed";
export type ShelfOrdering = "name" | "-name" | "item_count" | "-item_count";
export type ShelfScope = "personal" | "shared" | "group";
export type ShelfItemOrdering = "position" | "-position" | "title" | "-title" | "author" | "-author";

export interface ShelfOwnerUser { profileId: string; username: string; }
export interface ShelfOwnerGroup { id: string; name: string; isPublicGroup: boolean; }
export interface ShelfSummary {
  id: string;
  name: string;
  description: string;
  ownerType: ShelfOwnerType;
  ownerUser: ShelfOwnerUser | null;
  ownerGroup: ShelfOwnerGroup | null;
  visibility: ShelfVisibility;
  itemCount: number;
  matchedItemId?: string | null;
  canEdit: boolean;
  previewBooks?: BookPreview[];
}
export interface CreateShelfInput { name: string; description: string; ownerType: ShelfOwnerType; ownerGroupId?: string; visibility: ShelfVisibility; }
export interface UpdateShelfInput { name?: string; description?: string; visibility?: ShelfVisibility; }
export interface AddShelfItemInput { bookId: string; }
export interface ShelvesQuery {
  scope?: ShelfScope;
  ownerGroupId?: string;
  bookId?: string;
  ordering?: ShelfOrdering;
  includePreviewBooks?: boolean;
  previewLimit?: number;
  page?: number;
  pageSize?: number;
}
export interface ShelfItemsQuery { ordering?: ShelfItemOrdering; page?: number; pageSize?: number; }
export interface ShelfEditorItemsQuery { page?: number; pageSize?: number; }
export interface ShelfItem { id: string; shelfId: string; book: CompactBook; position: number; addedBy: ShelfOwnerUser | null; }
export type ShelfEditorItem =
  | { id: string; shelfId: string; position: number; unavailable: false; book: CompactBook; addedBy: ShelfOwnerUser | null }
  | { id: string; shelfId: string; position: number; unavailable: true; book: null; addedBy: ShelfOwnerUser | null };
export interface ShelfEditorItemsPage extends Page<ShelfEditorItem> { visibleItemCount: number; unavailableItemCount: number; }
