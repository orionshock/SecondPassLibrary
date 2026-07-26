import { describe, expect, it } from "vitest";

import {
  ApiError,
  addBookToGroup,
  createGroup,
  getGroup,
  listAllLibraryGroups,
  listGroupBooks,
  listGroupMembers,
  listGroups,
  removeBookFromGroup,
  updateGroup,
} from "@second-pass/spl-api";
import type { ApiClient } from "../../packages/spl-api/src/client";

describe("Library Groups SDK", () => {
  it("maps paginated group reads and crawls the all-groups picker", async () => {
    const calls: string[] = [];
    const responses = [
      { count: 1, next: null, previous: null, results: [{ id: "g1", name: "Readers", description: "Visible", is_public_group: false }] },
      { count: 2, next: "/api/v1/library/groups/?ordering=name&page=2&page_size=200", previous: null, results: [{ id: "public", name: "Common Room", description: "Public", is_public_group: true }] },
      { count: 2, next: null, previous: "previous", results: [{ id: "g2", name: "Test Group", description: "", is_public_group: false }] },
    ];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return responses.shift() as T; } };

    await expect(listGroups({ q: " readers ", ordering: "-name", page: 2, pageSize: 30 }, client)).resolves.toMatchObject({
      items: [{ id: "g1", name: "Readers", description: "Visible", isPublicGroup: false }],
    });
    await expect(listAllLibraryGroups(client)).resolves.toEqual([
      { id: "public", name: "Common Room", description: "Public", isPublicGroup: true },
      { id: "g2", name: "Test Group", description: "", isPublicGroup: false },
    ]);
    expect(calls).toEqual([
      "/api/v1/library/groups/?q=readers&ordering=-name&page=2&page_size=30",
      "/api/v1/library/groups/?ordering=name&page_size=200",
      "/api/v1/library/groups/?ordering=name&page=2&page_size=200",
    ]);
  });

  it("maps preview reads, compact Group Books, and username-only memberships", async () => {
    const calls: string[] = [];
    const compactBook = {
      id: "book", title: "Book", sort_title: "Book", subtitle: "Hidden subtitle",
      authors: [{ id: "author", name: "Author" }],
      series: null, catalog_tags: [], language: "eng", publisher: "Publisher",
      published_year: null, published_month: null, published_day: null,
      published_date_precision: "", cover_url: null, file_format: "EPUB",
    };
    const responses = [
      { id: "group/id", name: "Readers", description: "Visible", is_public_group: false, preview_books: [{ id: "preview", title: "Preview", cover_url: "/cover.jpg" }] },
      { count: 1, next: null, previous: null, results: [compactBook] },
      { count: 1, next: null, previous: null, results: [{
        id: "internal-membership", role: "hidden", created_at: "hidden", updated_at: "hidden",
        user: { profile_id: "profile", username: "reader", email: "hidden" }, is_curator: true,
      }] },
    ];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return responses.shift() as T;
    } };

    await expect(getGroup("group/id", { includePreviewBooks: true }, client)).resolves.toEqual({
      id: "group/id", name: "Readers", description: "Visible", isPublicGroup: false,
      previewBooks: [{ id: "preview", title: "Preview", coverUrl: "/cover.jpg" }],
    });
    await expect(listGroupBooks("group/id", {
      q: " book ", tag: "fantasy", excludeShelfId: "shelf/id", ordering: "-author", page: 2, pageSize: 30,
    }, client)).resolves.toMatchObject({
      items: [{
        id: "book", title: "Book", authors: [{ id: "author", name: "Author" }],
        catalogTags: [], fileFormat: "EPUB",
      }],
    });
    const members = await listGroupMembers("group/id", { page: 3, pageSize: 40 }, client);
    expect(members.items).toEqual([{
      user: { profileId: "profile", username: "reader" }, isCurator: true,
    }]);
    expect(members.items[0]).not.toHaveProperty("id");
    expect(members.items[0]).not.toHaveProperty("role");
    expect(members.items[0]).not.toHaveProperty("createdAt");
    expect(calls).toEqual([
      "/api/v1/library/groups/group%2Fid/?include_preview_books=true",
      "/api/v1/library/groups/group%2Fid/books/?q=book&tag=fantasy&exclude_shelf=shelf%2Fid&ordering=-author&page=2&page_size=30",
      "/api/v1/library/groups/group%2Fid/memberships/?page=3&page_size=40",
    ]);
  });

  it("requests preview Books explicitly for Group list rows", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 0, next: null, previous: null, results: [] } as T;
    } };
    await listGroups({ includePreviewBooks: true }, client);
    expect(calls).toEqual(["/api/v1/library/groups/?include_preview_books=true"]);
  });

  it("uses the exact immediate assignment mutation contracts", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return { id: "assignment", group_id: "group/id", book_id: "book/id" } as T;
    } };

    await expect(addBookToGroup("group/id", "book/id", client)).resolves.toEqual({
      id: "assignment", groupId: "group/id", bookId: "book/id",
    });
    await removeBookFromGroup("group/id", "book/id", client);

    expect(calls[0]).toMatchObject({
      path: "/api/v1/library/groups/group%2Fid/books/",
      init: { method: "POST", body: JSON.stringify({ book_id: "book/id" }) },
    });
    expect(calls[1]).toEqual({
      path: "/api/v1/library/groups/group%2Fid/books/book%2Fid/",
      init: { method: "DELETE" },
    });
  });

  it("maps injected wire-format Book assignment field errors", async () => {
    const client: ApiClient = { request: async () => {
      throw new ApiError("Invalid.", 400, { fields: { book_id: ["Choose a visible Book."] } });
    } };
    await expect(addBookToGroup("group", "book", client)).rejects.toMatchObject({
      fields: { bookId: ["Choose a visible Book."] },
    });
  });

  it("uses exact Group metadata create and partial-update contracts", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return {
        id: "group/id", name: "Readers", description: "Updated", is_public_group: false,
      } as T;
    } };

    await expect(createGroup({ name: "Readers", description: "Created" }, client)).resolves.toEqual({
      id: "group/id", name: "Readers", description: "Updated", isPublicGroup: false,
    });
    await updateGroup("group/id", { name: "Readers", description: "Updated" }, client);
    await updateGroup("group/id", { description: "Description only" }, client);

    expect(calls).toEqual([
      {
        path: "/api/v1/library/groups/",
        init: {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "Readers", description: "Created" }),
        },
      },
      {
        path: "/api/v1/library/groups/group%2Fid/",
        init: {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name: "Readers", description: "Updated" }),
        },
      },
      {
        path: "/api/v1/library/groups/group%2Fid/",
        init: {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ description: "Description only" }),
        },
      },
    ]);
  });

  it("preserves Group metadata field errors under app-facing field names", async () => {
    const error = new ApiError("Invalid.", 400, {
      fields: { name: ["Name is required."], description: ["Invalid description."] },
    });
    const client: ApiClient = { request: async () => { throw error; } };

    await expect(createGroup({ name: "", description: "" }, client)).rejects.toBe(error);
    await expect(updateGroup("group", { name: "" }, client)).rejects.toBe(error);
  });
});
