import { describe, expect, it } from "vitest";

import { collectPaginatedResults, toPage, type ApiPage } from "../../packages/spl-api/src/pagination";

describe("toPage", () => {
  it("maps server results to stable app items", () => {
    const page = toPage(
      { results: [{ server_name: "Shelf" }], count: 1, next: null, previous: null },
      (item) => ({ name: item.server_name }),
    );

    expect(page).toEqual({ items: [{ name: "Shelf" }], count: 1, next: null, previous: null });
  });

  it("collects mapped items from every next page in server order", async () => {
    const calls: string[] = [];
    const pages: Record<string, ApiPage<{ id: string }>> = {
      "/items?page_size=200": {
        results: [{ id: "first" }], count: 2, next: "/items?page=2&page_size=200", previous: null,
      },
      "/items?page=2&page_size=200": {
        results: [{ id: "second" }], count: 2, next: null, previous: "/items?page_size=200",
      },
    };

    await expect(collectPaginatedResults(
      "/items?page_size=200",
      async (path) => { calls.push(path); return pages[path]!; },
      ({ id }) => id.toUpperCase(),
    )).resolves.toEqual(["FIRST", "SECOND"]);
    expect(calls).toEqual(["/items?page_size=200", "/items?page=2&page_size=200"]);
  });

  it("follows absolute server pagination links through the same-origin API path", async () => {
    const calls: string[] = [];
    const pages: Record<string, ApiPage<{ id: string }>> = {
      "/api/v1/library/authors/?page_size=200": {
        results: [{ id: "first" }],
        count: 2,
        next: "http://127.0.0.1:8000/api/v1/library/authors/?page=2&page_size=200",
        previous: null,
      },
      "/api/v1/library/authors/?page=2&page_size=200": {
        results: [{ id: "second" }], count: 2, next: null, previous: null,
      },
    };

    await expect(collectPaginatedResults(
      "/api/v1/library/authors/?page_size=200",
      async (path) => { calls.push(path); return pages[path]!; },
      ({ id }) => id,
    )).resolves.toEqual(["first", "second"]);
    expect(calls).toEqual([
      "/api/v1/library/authors/?page_size=200",
      "/api/v1/library/authors/?page=2&page_size=200",
    ]);
  });
});
