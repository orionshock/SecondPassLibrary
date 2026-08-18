import { describe, expect, it } from "vitest";

import {
  ApiError,
  addBookToGroup,
  addGroupMember,
  createGroup,
  deleteGroup,
  getGroup,
  listAllLibraryGroups,
  listAllGroupsForBook,
  listGroupAuthors,
  listGroupBooks,
  listGroupMembers,
  listGroupSeries,
  listGroupTags,
  listGroups,
  removeBookFromGroup,
  removeGroupMember,
  searchGroupBooks,
  updateGroup,
  updateGroupMember,
} from "@second-pass/spl-api";
import type { ApiClient } from "../../client";

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
      q: " book ", tag: "fantasy", authorId: "author/id", seriesId: "series/id",
      publisher: "A Press", excludeShelfId: "shelf/id", ordering: "-author", page: 2, pageSize: 30,
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
      "/api/v1/library/groups/group%2Fid/books/?q=book&tag=fantasy&author=author%2Fid&series=series%2Fid&publisher=A+Press&exclude_shelf=shelf%2Fid&ordering=-author&page=2&page_size=30",
      "/api/v1/library/groups/group%2Fid/memberships/?page=3&page_size=40",
    ]);
  });

  it("maps Group broad search and scoped axes through the shared Library wire models", async () => {
    const calls: string[] = [];
    const responses = [
      { count: 0, next: null, previous: null, results: [] },
      { count: 1, next: null, previous: null, results: [{ id: "a1", name: "Ada", sort_name: "Ada", biography: "", book_count: 2, preview_books: [] }] },
      { count: 1, next: null, previous: null, results: [{ id: "s1", name: "Saga", sort_name: "Saga", summary: "", book_count: 1 }] },
      { count: 1, next: null, previous: null, results: [{ id: "t1", name: "Fantasy", slug: "fantasy", book_count: 3 }] },
    ];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return responses.shift() as T;
    } };

    await searchGroupBooks("group/id", {
      q: " Book ", excludeShelfId: "shelf/id", ordering: "-series", page: 2, pageSize: 30,
    }, client);
    await expect(listGroupAuthors("group/id", {
      q: " Ada ", excludeId: "author/id", tag: "history", ordering: "-book_count",
      includePreviewBooks: true, previewLimit: 4, page: 2, pageSize: 20,
    }, client)).resolves.toMatchObject({ items: [{ id: "a1", bookCount: 2, previewBooks: [] }] });
    await expect(listGroupSeries("group/id", { q: " Saga " }, client)).resolves.toMatchObject({
      items: [{ id: "s1", bookCount: 1 }],
    });
    await expect(listGroupTags("group/id", { q: " Fantasy ", ordering: "-book_count" }, client)).resolves.toMatchObject({
      items: [{ id: "t1", bookCount: 3 }],
    });

    expect(calls).toEqual([
      "/api/v1/library/groups/group%2Fid/search?q=Book&exclude_shelf=shelf%2Fid&ordering=-series&page=2&page_size=30",
      "/api/v1/library/groups/group%2Fid/authors/?q=Ada&exclude_id=author%2Fid&tag=history&ordering=-book_count&include_preview_books=true&preview_limit=4&page=2&page_size=20",
      "/api/v1/library/groups/group%2Fid/series/?q=Saga",
      "/api/v1/library/groups/group%2Fid/tags/?q=Fantasy&ordering=-book_count",
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

  it("serializes bounded Group preview limits and maps validation errors", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return path.includes("groups/group")
        ? { id: "group", name: "Group", description: "", is_public_group: false } as T
        : { count: 0, next: null, previous: null, results: [] } as T;
    } };

    await listGroups({ previewLimit: 0 }, client);
    await getGroup("group", { includePreviewBooks: true, previewLimit: 24 }, client);

    expect(calls).toEqual([
      "/api/v1/library/groups/?preview_limit=0",
      "/api/v1/library/groups/group/?include_preview_books=true&preview_limit=24",
    ]);

    const invalidClient: ApiClient = { request: async () => {
      throw new ApiError("Invalid.", 400, {
        fields: { preview_limit: ["Must be an integer from 0 to 24."] },
      });
    } };
    await expect(listGroups({ previewLimit: 25 }, invalidClient)).rejects.toMatchObject({
      fields: { previewLimit: ["Must be an integer from 0 to 24."] },
    });
  });

  it("serializes the Book filter with existing Group list query options", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 0, next: null, previous: null, results: [] } as T;
    } };

    await listGroups({
      q: " readers ",
      bookId: "book/id",
      ordering: "-name",
      includePreviewBooks: true,
      page: 2,
      pageSize: 30,
    }, client);

    expect(calls).toEqual([
      "/api/v1/library/groups/?q=readers&book=book%2Fid&ordering=-name&include_preview_books=true&page=2&page_size=30",
    ]);
  });

  it("collects every preview-bearing Group page for a Book", async () => {
    const calls: string[] = [];
    const responses = [
      {
        count: 2,
        next: "/api/v1/library/groups/?book=book-id&ordering=name&include_preview_books=true&preview_limit=12&page=2&page_size=200",
        previous: null,
        results: [{ id: "g1", name: "First", description: "", is_public_group: false, preview_books: [] }],
      },
      {
        count: 2,
        next: null,
        previous: "previous",
        results: [{ id: "g2", name: "Second", description: "", is_public_group: false, preview_books: [{ id: "preview", title: "Preview", cover_url: null }] }],
      },
    ];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return responses.shift() as T;
    } };

    await expect(listAllGroupsForBook("book-id", 12, client)).resolves.toEqual([
      { id: "g1", name: "First", description: "", isPublicGroup: false, previewBooks: [] },
      { id: "g2", name: "Second", description: "", isPublicGroup: false, previewBooks: [{ id: "preview", title: "Preview", coverUrl: null }] },
    ]);
    expect(calls).toEqual([
      "/api/v1/library/groups/?book=book-id&ordering=name&include_preview_books=true&preview_limit=12&page_size=200",
      "/api/v1/library/groups/?book=book-id&ordering=name&include_preview_books=true&preview_limit=12&page=2&page_size=200",
    ]);
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

  it("uses canonical Group membership mutation contracts", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return { user: { profile_id: "profile/id", username: "reader" }, is_curator: true } as T;
    } };

    await expect(addGroupMember("group/id", { userId: "profile/id", isCurator: true }, client)).resolves.toEqual({
      user: { profileId: "profile/id", username: "reader" }, isCurator: true,
    });
    await expect(updateGroupMember("group/id", "profile/id", { isCurator: false }, client)).resolves.toMatchObject({
      user: { profileId: "profile/id" }, isCurator: true,
    });
    await removeGroupMember("group/id", "profile/id", client);

    expect(calls).toEqual([
      {
        path: "/api/v1/library/groups/group%2Fid/memberships/",
        init: {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ user_id: "profile/id", is_curator: true }),
        },
      },
      {
        path: "/api/v1/library/groups/group%2Fid/memberships/profile%2Fid/",
        init: {
          method: "PATCH", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ is_curator: false }),
        },
      },
      {
        path: "/api/v1/library/groups/group%2Fid/memberships/profile%2Fid/",
        init: { method: "DELETE" },
      },
    ]);
  });

  it("maps membership mutation fields without admitting role controls", async () => {
    const client: ApiClient = { request: async () => {
      throw new ApiError("Invalid.", 400, {
        fields: { user_id: ["Choose a user."], is_curator: ["Not allowed."], role: ["Unknown field."] },
      });
    } };
    await expect(addGroupMember("group", { userId: "profile", isCurator: false }, client)).rejects.toMatchObject({
      fields: { userId: ["Choose a user."], isCurator: ["Not allowed."], role: ["Unknown field."] },
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

  it("uses the custom Group DELETE contract and preserves structured failures", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return undefined as T;
    } };
    await expect(deleteGroup("group/id", client)).resolves.toBeUndefined();
    expect(calls).toEqual([{
      path: "/api/v1/library/groups/group%2Fid/",
      init: { method: "DELETE" },
    }]);

    const error = new ApiError("Public cannot be deleted.", 400, {
      fields: { detail: ["Public cannot be deleted."] },
    });
    const failing: ApiClient = { request: async () => { throw error; } };
    await expect(deleteGroup("public", failing)).rejects.toBe(error);
  });
});
