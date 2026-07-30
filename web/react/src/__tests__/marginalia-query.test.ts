import { describe, expect, it } from "vitest";

import { marginaliaListSdkQuery, marginaliaListSearchParams, marginaliaListStateFromSearchParams, withMarginaliaListChange } from "../features/marginalia/marginaliaQuery";
import { marginaliaExportSdkQuery, marginaliaExportStateFromSearchParams } from "../features/marginalia/marginaliaExportQuery";

describe("My Marginalia list query", () => {
  it("canonicalizes defaults and invalid values", () => {
    const defaults = marginaliaListStateFromSearchParams(new URLSearchParams());
    expect(defaults).toEqual({ q: "", status: "all", page: 1, pageSize: 20 });
    expect(marginaliaListSearchParams(defaults).toString()).toBe("");
    expect(marginaliaListStateFromSearchParams(new URLSearchParams("status=bad&page=0&page_size=200"))).toEqual(defaults);
  });

  it("maps All, Active, and Closed directly to the canonical Marginalia contract", () => {
    expect(marginaliaListSdkQuery(marginaliaListStateFromSearchParams(new URLSearchParams())))
      .toEqual({ page: 1, pageSize: 20 });

    const active = marginaliaListStateFromSearchParams(new URLSearchParams("status=active&page=2&page_size=40&q=notes"));
    expect(marginaliaListSearchParams(active).toString()).toBe("status=active&page=2&page_size=40&q=notes");
    expect(marginaliaListSdkQuery(active)).toEqual({ q: "notes", status: "active", page: 2, pageSize: 40 });

    const closed = marginaliaListStateFromSearchParams(new URLSearchParams("status=closed"));
    expect(marginaliaListSdkQuery(closed)).toEqual({ status: "closed", page: 1, pageSize: 20 });
  });

  it("resets the page for search, status, and page-size changes", () => {
    const current = marginaliaListStateFromSearchParams(new URLSearchParams("page=4&page_size=40"));
    expect(withMarginaliaListChange(current, { q: "new" }).page).toBe(1);
    expect(withMarginaliaListChange(current, { status: "closed" }).page).toBe(1);
    expect(withMarginaliaListChange(current, { pageSize: 30 }).page).toBe(1);
    expect(withMarginaliaListChange(current, { page: 2 }, false).page).toBe(2);
  });
});

describe("Marginalia Export legacy query isolation", () => {
  it("preserves the existing Export status mapping while its backend remains on reading.ts", () => {
    const historical = marginaliaExportStateFromSearchParams(new URLSearchParams("status=historical"));
    expect(marginaliaExportSdkQuery(historical)).toEqual({ isActive: false, page: 1, pageSize: 20 });
  });
});
