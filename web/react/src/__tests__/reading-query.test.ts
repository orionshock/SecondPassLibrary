import { describe, expect, it } from "vitest";

import { readingListSdkQuery, readingListSearchParams, readingListStateFromSearchParams, withReadingListChange } from "../features/reading/readingQuery";

describe("My Marginalia list query", () => {
  it("canonicalizes defaults and invalid values", () => {
    const defaults = readingListStateFromSearchParams(new URLSearchParams());
    expect(defaults).toEqual({ q: "", status: "all", page: 1, pageSize: 20 });
    expect(readingListSearchParams(defaults).toString()).toBe("");
    expect(readingListStateFromSearchParams(new URLSearchParams("status=bad&page=0&page_size=200"))).toEqual(defaults);
  });

  it("maps active and historical product filters to the API is_active contract", () => {
    const active = readingListStateFromSearchParams(new URLSearchParams("status=active&page=2&page_size=40&q=notes"));
    expect(readingListSearchParams(active).toString()).toBe("status=active&page=2&page_size=40&q=notes");
    expect(readingListSdkQuery(active)).toEqual({ q: "notes", isActive: true, page: 2, pageSize: 40 });

    const historical = readingListStateFromSearchParams(new URLSearchParams("status=historical"));
    expect(readingListSdkQuery(historical)).toEqual({ isActive: false, page: 1, pageSize: 20 });
  });

  it("resets the page for search, status, and page-size changes", () => {
    const current = readingListStateFromSearchParams(new URLSearchParams("page=4&page_size=40"));
    expect(withReadingListChange(current, { q: "new" }).page).toBe(1);
    expect(withReadingListChange(current, { status: "historical" }).page).toBe(1);
    expect(withReadingListChange(current, { pageSize: 30 }).page).toBe(1);
    expect(withReadingListChange(current, { page: 2 }, false).page).toBe(2);
  });
});
