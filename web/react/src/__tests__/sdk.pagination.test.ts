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
});
