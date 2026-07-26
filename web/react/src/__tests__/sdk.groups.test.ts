import { describe, expect, it } from "vitest";

import {
  ApiError,
  addBookToGroup,
  listAllLibraryGroups,
  listGroups,
  removeBookFromGroup,
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
});
