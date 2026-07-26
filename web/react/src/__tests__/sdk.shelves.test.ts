import { describe, expect, it } from "vitest";

import {
  ApiError,
  addShelfItem,
  createShelf,
  deleteShelf,
  getShelf,
  listAllShelvesForBook,
  listShelfItems,
  listShelves,
  removeShelfItem,
  updateShelf,
} from "@second-pass/spl-api";
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
  preview_books: [{ id: "book", title: "Preview", cover_url: "/cover.jpg" }],
};

const compactBook = {
  id: "book",
  title: "Book",
  sort_title: "Book",
  subtitle: "Subtitle",
  authors: [{ id: "author", name: "Author" }],
  series: { id: "series", name: "Series", sort_name: "Series", series_index: "1.0" },
  catalog_tags: [{ id: "tag", name: "Tag", slug: "tag" }],
  language: "eng",
  publisher: "Publisher",
  published_year: 2025,
  published_month: null,
  published_day: null,
  published_date_precision: "year",
  cover_url: "/book-cover.jpg",
  file_format: "epub",
};

describe("Shelves SDK", () => {
  it("maps create, update, and delete to the strict Shelf mutation contract", async () => {
    const calls: Array<{ path: string; options?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, options?: RequestInit) => {
      calls.push({ path, options });
      return personalShelf as T;
    } };

    const created = await createShelf({
      name: "Current Favorites",
      description: "Favorites",
      ownerType: "group",
      ownerGroupId: "group/id",
      visibility: "private",
    }, client);
    await updateShelf("shelf/id", {
      name: "Renamed",
      description: "",
      visibility: undefined,
    }, client);
    await deleteShelf("shelf/id", client);

    expect(created.name).toBe("Current Favorites");
    expect(calls.map(({ path }) => path)).toEqual([
      "/api/v1/shelves/",
      "/api/v1/shelves/shelf%2Fid/",
      "/api/v1/shelves/shelf%2Fid/",
    ]);
    expect(calls[0]?.options?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.options?.body))).toEqual({
      name: "Current Favorites",
      description: "Favorites",
      owner_type: "group",
      visibility: "private",
      owner_group: "group/id",
    });
    expect(calls[1]?.options?.method).toBe("PATCH");
    expect(JSON.parse(String(calls[1]?.options?.body))).toEqual({
      name: "Renamed",
      description: "",
    });
    expect(calls[2]?.options).toEqual({ method: "DELETE" });
    for (const forbidden of ["owner_user", "can_edit", "item_count", "preview_books", "matched_item_id"] as const) {
      expect(JSON.parse(String(calls[0]?.options?.body))).not.toHaveProperty(forbidden);
    }
  });

  it("maps Shelf mutation field errors to app-facing names", async () => {
    const client: ApiClient = { request: async () => {
      throw new ApiError("Invalid.", 400, {
        fields: { owner_type: ["Invalid owner."], owner_group: ["Choose a group."] },
      });
    } };

    await expect(createShelf({
      name: "Shelf",
      description: "",
      ownerType: "group",
      ownerGroupId: "group",
      visibility: "private",
    }, client)).rejects.toMatchObject({
      fields: { ownerType: ["Invalid owner."], ownerGroupId: ["Choose a group."] },
    });
  });

  it("maps list query and explicitly picks the app-facing shelf contract", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: null, previous: null, results: [personalShelf] } as T;
    } };

    const page = await listShelves({
      scope: "shared",
      ownerGroupId: "group/id",
      bookId: "book/id",
      ordering: "-item_count",
      includePreviewBooks: true,
      page: 2,
      pageSize: 30,
    }, client);

    expect(calls).toEqual(["/api/v1/shelves/?scope=shared&owner_group=group%2Fid&book=book%2Fid&ordering=-item_count&include_preview_books=true&page=2&page_size=30"]);
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
      previewBooks: [{ id: "book", title: "Preview", coverUrl: "/cover.jpg" }],
    }]);
    expect(page.items[0]).not.toHaveProperty("created_at");
    expect(page.items[0]).not.toHaveProperty("updated_at");
    expect(page.items[0]).not.toHaveProperty("preview_books");
  });

  it("maps detail and Shelf items through the compact Book contract", async () => {
    const calls: string[] = [];
    const responses = [
      personalShelf,
      {
        count: 1,
        next: null,
        previous: null,
        results: [{
          id: "item",
          shelf: "shelf/id",
          book: { ...compactBook, description: "not-app-facing", groups: [] },
          position: 0,
          added_by: { profile_id: "adder", username: "reader" },
          created_at: "not-app-facing",
          updated_at: "not-app-facing",
        }],
      },
    ];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return responses.shift() as T;
    } };

    const shelf = await getShelf("shelf/id", { includePreviewBooks: true }, client);
    const items = await listShelfItems("shelf/id", { ordering: "author", page: 2, pageSize: 40 }, client);

    expect(calls).toEqual([
      "/api/v1/shelves/shelf%2Fid/?include_preview_books=true",
      "/api/v1/shelves/shelf%2Fid/items/?ordering=author&page=2&page_size=40",
    ]);
    expect(shelf.previewBooks).toEqual([{ id: "book", title: "Preview", coverUrl: "/cover.jpg" }]);
    expect(items.items[0]).toMatchObject({
      id: "item",
      shelfId: "shelf/id",
      position: 0,
      addedBy: { profileId: "adder", username: "reader" },
      book: {
        id: "book",
        title: "Book",
        series: { id: "series", name: "Series", seriesIndex: "1.0" },
        catalogTags: [{ id: "tag", name: "Tag", slug: "tag" }],
      },
    });
    expect(items.items[0]).not.toHaveProperty("created_at");
    expect(items.items[0].book).not.toHaveProperty("description");
    expect(items.items[0].book).not.toHaveProperty("groups");
  });

  it("uses the immediate Shelf item add/remove contracts", async () => {
    const calls: Array<{ path: string; options?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, options?: RequestInit) => {
      calls.push({ path, options });
      return {
        id: "item", shelf: "shelf/id", book: compactBook, position: 0, added_by: null,
      } as T;
    } };

    await expect(addShelfItem("shelf/id", { bookId: "book/id" }, client)).resolves.toMatchObject({
      id: "item", shelfId: "shelf/id", book: { id: "book", title: "Book" },
    });
    await removeShelfItem("shelf/id", "item/id", client);

    expect(calls.map(({ path, options }) => [path, options?.method])).toEqual([
      ["/api/v1/shelves/shelf%2Fid/items/", "POST"],
      ["/api/v1/shelves/shelf%2Fid/items/item%2Fid/", "DELETE"],
    ]);
    expect(JSON.parse(String(calls[0]?.options?.body))).toEqual({ book: "book/id" });
    expect(calls[1]?.options).toEqual({ method: "DELETE" });

    const failing: ApiClient = { request: async () => {
      throw new ApiError("Duplicate.", 400, { fields: { book: ["Already on shelf."] } });
    } };
    await expect(addShelfItem("shelf", { bookId: "book" }, failing)).rejects.toMatchObject({
      fields: { bookId: ["Already on shelf."] },
    });
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
