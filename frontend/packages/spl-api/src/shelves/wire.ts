import type { CompactBookResponse } from "../library/compactBooks";
import type { ApiPage } from "../pagination";
import type { ShelfOwnerType, ShelfVisibility } from "./types";

export interface ShelfOwnerUserResponse { profile_id: string; username: string; }
export interface ShelfSummaryResponse {
  id: string;
  name: string;
  description: string;
  owner_type: ShelfOwnerType;
  owner_user: ShelfOwnerUserResponse | null;
  owner_group: { id: string; name: string; is_public_group: boolean } | null;
  visibility: ShelfVisibility;
  item_count: number;
  matched_item_id?: string | null;
  can_edit: boolean;
  preview_books?: Array<{ id: string; title: string; cover_url: string | null }>;
}
export interface ShelfItemResponse { id: string; shelf: string; book: CompactBookResponse; position: number; added_by: ShelfOwnerUserResponse | null; }
export interface ShelfEditorItemResponse { id: string; shelf: string; book: CompactBookResponse | null; position: number; unavailable: boolean; added_by: ShelfOwnerUserResponse | null; }
export interface ShelfEditorItemsPageResponse extends ApiPage<ShelfEditorItemResponse> { visible_item_count: number; unavailable_item_count: number; }
