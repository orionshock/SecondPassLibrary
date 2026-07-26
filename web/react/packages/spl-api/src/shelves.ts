import { apiClient, type ApiClient } from "./client";
import { toPage, type ApiPage, type Page } from "./pagination";

export type ShelfOwnerType = "user" | "group";
export type ShelfVisibility = "private" | "listed";
export type ShelfOrdering = "name" | "-item_count";

export interface ShelfOwnerUser {
  profileId: string;
  username: string;
}

export interface ShelfOwnerGroup {
  id: string;
  name: string;
  isPublicGroup: boolean;
}

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
}

export interface ShelvesQuery {
  bookId?: string;
  ordering?: ShelfOrdering;
  page?: number;
  pageSize?: number;
}

interface ShelfOwnerUserResponse {
  profile_id: string;
  username: string;
}

interface ShelfOwnerGroupResponse {
  id: string;
  name: string;
  is_public_group: boolean;
}

interface ShelfSummaryResponse {
  id: string;
  name: string;
  description: string;
  owner_type: ShelfOwnerType;
  owner_user: ShelfOwnerUserResponse | null;
  owner_group: ShelfOwnerGroupResponse | null;
  visibility: ShelfVisibility;
  item_count: number;
  matched_item_id?: string | null;
  can_edit: boolean;
}

export async function listShelves(
  query: ShelvesQuery = {},
  client: ApiClient = apiClient,
): Promise<Page<ShelfSummary>> {
  const parameters = new URLSearchParams();
  if (query.bookId) parameters.set("book", query.bookId);
  if (query.ordering) parameters.set("ordering", query.ordering);
  if (query.page) parameters.set("page", String(query.page));
  if (query.pageSize) parameters.set("page_size", String(query.pageSize));
  const suffix = parameters.size ? `?${parameters.toString()}` : "";
  return toPage(
    await client.request<ApiPage<ShelfSummaryResponse>>(`/api/v1/shelves/${suffix}`),
    mapShelfSummary,
  );
}

export async function listAllShelvesForBook(
  bookId: string,
  client: ApiClient = apiClient,
): Promise<ShelfSummary[]> {
  const shelves: ShelfSummary[] = [];
  const parameters = new URLSearchParams({
    book: bookId,
    ordering: "name",
    page_size: "200",
  });
  let path: string | null = `/api/v1/shelves/?${parameters.toString()}`;

  while (path) {
    const page: ApiPage<ShelfSummaryResponse> = await client.request<ApiPage<ShelfSummaryResponse>>(path);
    shelves.push(...page.results.map(mapShelfSummary));
    path = page.next;
  }

  return shelves;
}

function mapShelfSummary(response: ShelfSummaryResponse): ShelfSummary {
  return {
    id: response.id,
    name: response.name,
    description: response.description,
    ownerType: response.owner_type,
    ownerUser: response.owner_user ? {
      profileId: response.owner_user.profile_id,
      username: response.owner_user.username,
    } : null,
    ownerGroup: response.owner_group ? {
      id: response.owner_group.id,
      name: response.owner_group.name,
      isPublicGroup: response.owner_group.is_public_group,
    } : null,
    visibility: response.visibility,
    itemCount: response.item_count,
    ...(response.matched_item_id !== undefined ? { matchedItemId: response.matched_item_id } : {}),
    canEdit: response.can_edit,
  };
}
