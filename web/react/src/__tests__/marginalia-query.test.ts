import { describe, expect, it } from "vitest";

import { marginaliaListSdkQuery, marginaliaListSearchParams, marginaliaListStateFromSearchParams, withMarginaliaListChange } from "../features/marginalia/marginaliaQuery";

describe("My Marginalia list query", () => {
  it("canonicalizes defaults and invalid values", () => {
    const defaults = marginaliaListStateFromSearchParams(new URLSearchParams());
    expect(defaults).toEqual({ q: "", status: "all", page: 1, pageSize: 20 });
    expect(marginaliaListSearchParams(defaults).toString()).toBe("");
    expect(marginaliaListStateFromSearchParams(new URLSearchParams("status=bad&page=0&page_size=200"))).toEqual(defaults);
  });

  it("maps active and historical product filters to the API is_active contract", () => {
    const active = marginaliaListStateFromSearchParams(new URLSearchParams("status=active&page=2&page_size=40&q=notes"));
    expect(marginaliaListSearchParams(active).toString()).toBe("status=active&page=2&page_size=40&q=notes");
    expect(marginaliaListSdkQuery(active)).toEqual({ q: "notes", isActive: true, page: 2, pageSize: 40 });

    const historical = marginaliaListStateFromSearchParams(new URLSearchParams("status=historical"));
    expect(marginaliaListSdkQuery(historical)).toEqual({ isActive: false, page: 1, pageSize: 20 });
  });

  it("resets the page for search, status, and page-size changes", () => {
    const current = marginaliaListStateFromSearchParams(new URLSearchParams("page=4&page_size=40"));
    expect(withMarginaliaListChange(current, { q: "new" }).page).toBe(1);
    expect(withMarginaliaListChange(current, { status: "historical" }).page).toBe(1);
    expect(withMarginaliaListChange(current, { pageSize: 30 }).page).toBe(1);
    expect(withMarginaliaListChange(current, { page: 2 }, false).page).toBe(2);
  });
});
