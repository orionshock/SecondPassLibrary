import { describe, expect, it } from "vitest";

import { listAllShelvesForBook, listShelves } from "@second-pass/spl-api";
import type { ApiClient } from "../../packages/spl-api/src/client";

const personalShelf = {
  id: "personal",
  name: "Current Favorites",
  description: "Favorites",
  owner_type: "user",
  owner_user: { profile_id: "profile", username: "reader" },
  owner_group: null,
  visibility: "listed",
  item_count: 12,
  matched_item_id: "item",
  can_edit: true,
  created_at: "not-app-facing",
  updated_at: "not-app-facing",
  preview_books: [{ id: "book" }],
};

describe("Shelves SDK", () => {
  it("maps list query and explicitly picks the app-facing shelf contract", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: null, previous: null, results: [personalShelf] } as T;
    } };

    const page = await listShelves({ bookId: "book/id", ordering: "-item_count", page: 2, pageSize: 30 }, client);

    expect(calls).toEqual(["/api/v1/shelves/?book=book%2Fid&ordering=-item_count&page=2&page_size=30"]);
    expect(page.items).toEqual([{
      id: "personal",
      name: "Current Favorites",
      description: "Favorites",
      ownerType: "user",
      ownerUser: { profileId: "profile", username: "reader" },
      ownerGroup: null,
      visibility: "listed",
      itemCount: 12,
      matchedItemId: "item",
      canEdit: true,
    }]);
    expect(page.items[0]).not.toHaveProperty("created_at");
    expect(page.items[0]).not.toHaveProperty("updated_at");
    expect(page.items[0]).not.toHaveProperty("preview_books");
  });

  it("maps group ownership and follows every shelves-for-Book page", async () => {
    const calls: string[] = [];
    const groupShelf = {
      ...personalShelf,
      id: "group-shelf",
      name: "Sci-Fi Stack",
      owner_type: "group",
      owner_user: null,
      owner_group: { id: "public", name: "Common Room", is_public_group: true },
      visibility: "private",
      item_count: 10,
      matched_item_id: null,
      can_edit: false,
    };
    const responses = [
      { count: 2, next: "/api/v1/shelves/?book=book-id&ordering=name&page=2&page_size=200", previous: null, results: [personalShelf] },
      { count: 2, next: null, previous: "previous", results: [groupShelf] },
    ];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return responses.shift() as T;
    } };

    const shelves = await listAllShelvesForBook("book-id", client);

    expect(calls).toEqual([
      "/api/v1/shelves/?book=book-id&ordering=name&page_size=200",
      "/api/v1/shelves/?book=book-id&ordering=name&page=2&page_size=200",
    ]);
    expect(shelves.map(({ id }) => id)).toEqual(["personal", "group-shelf"]);
    expect(shelves[1].ownerGroup).toEqual({ id: "public", name: "Common Room", isPublicGroup: true });
  });
});
