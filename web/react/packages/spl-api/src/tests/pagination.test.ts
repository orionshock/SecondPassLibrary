import { describe, expect, it } from "vitest";

import { toPage } from "../pagination";

describe("toPage", () => {
  it("maps server results to stable app items", () => {
    const page = toPage(
      { results: [{ server_name: "Shelf" }], count: 1, next: null, previous: null },
      (item) => ({ name: item.server_name }),
    );

    expect(page).toEqual({ items: [{ name: "Shelf" }], count: 1, next: null, previous: null });
  });
});
