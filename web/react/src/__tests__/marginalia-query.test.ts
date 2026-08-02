import { describe, expect, it } from "vitest";

import {
  marginaliaBooksSdkQuery,
  marginaliaBookSessionsSdkQuery,
  marginaliaBrowseStage,
  marginaliaListSdkQuery,
  marginaliaListSearchParams,
  marginaliaListStateFromSearchParams,
  marginaliaPath,
  withMarginaliaBookSessionChange,
  withMarginaliaListChange,
  withMarginaliaSearch,
  withMarginaliaView,
  withSelectedMarginaliaBook,
} from "../features/marginalia/marginaliaQuery";
import { marginaliaExportCandidateQuery, marginaliaExportSdkQuery, marginaliaExportStateFromSearchParams } from "../features/marginalia/marginaliaExportQuery";

describe("My Marginalia list query", () => {
  it("canonicalizes defaults and invalid values", () => {
    const defaults = marginaliaListStateFromSearchParams(new URLSearchParams());
    expect(defaults).toEqual({
      view: "sessions", q: "", status: "all", page: 1, pageSize: 20,
      bookSessionQ: "", bookSessionStatus: "all", bookSessionPage: 1, bookSessionPageSize: 20,
    });
    expect(marginaliaBrowseStage(defaults)).toBe("sessions");
    expect(marginaliaListSearchParams(defaults).toString()).toBe("");
    expect(marginaliaListStateFromSearchParams(new URLSearchParams("view=bad&book=bad&status=bad&page=0&page_size=200"))).toEqual(defaults);
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

  it("uses durable Books and selected-Book stages with independent searches", () => {
    const bookId = "11111111-1111-4111-8111-111111111111";
    const selected = marginaliaListStateFromSearchParams(new URLSearchParams(
      `view=books&book=${bookId}&q=butcher&page=3&page_size=30&session_q=notes&session_status=closed&session_page=2&session_page_size=40`,
    ));
    expect(marginaliaBrowseStage(selected)).toBe("book-sessions");
    expect(marginaliaListSearchParams(selected).toString()).toBe(
      `view=books&book=${bookId}&page=3&page_size=30&q=butcher&session_status=closed&session_page=2&session_page_size=40&session_q=notes`,
    );
    expect(marginaliaBookSessionsSdkQuery(selected)).toEqual({ q: "notes", status: "closed", page: 2, pageSize: 40 });
    expect(marginaliaBooksSdkQuery(selected)).toEqual({ q: "butcher", page: 3, pageSize: 30 });
  });

  it("changes views and new searches reset Session status to All", () => {
    const closed = marginaliaListStateFromSearchParams(new URLSearchParams("status=closed&page=4&q=old"));
    const books = withMarginaliaView(closed, "books");
    expect(books).toMatchObject({ view: "books", q: "", status: "all", page: 1 });
    expect(marginaliaPath(books)).toBe("/marginalia?view=books");

    const searched = withMarginaliaSearch(closed, "new");
    expect(searched).toMatchObject({ q: "new", status: "all", page: 1 });

    const bookId = "11111111-1111-4111-8111-111111111111";
    const selected = withMarginaliaBookSessionChange(withSelectedMarginaliaBook({ ...books, q: "book search", page: 3 }, bookId), {
      bookSessionStatus: "closed",
      bookSessionPage: 4,
    });
    const sessionSearch = withMarginaliaSearch(selected, "session note");
    expect(sessionSearch).toMatchObject({
      q: "book search",
      page: 3,
      bookSessionQ: "session note",
      bookSessionStatus: "all",
      bookSessionPage: 1,
    });
    expect(withMarginaliaView(selected, "sessions").bookId).toBeUndefined();
  });

  it("preserves the Books-list URL state while entering and leaving a selected Book", () => {
    const bookId = "11111111-1111-4111-8111-111111111111";
    const books = marginaliaListStateFromSearchParams(new URLSearchParams("view=books&q=dune&page=2&page_size=30"));
    const selected = withSelectedMarginaliaBook(books, bookId);
    expect(marginaliaPath(selected)).toBe(`/marginalia?view=books&book=${bookId}&page=2&page_size=30&q=dune`);
    expect(marginaliaPath(withSelectedMarginaliaBook(selected))).toBe("/marginalia?view=books&page=2&page_size=30&q=dune");
  });
});

describe("Marginalia Export query", () => {
  it("maps All, Active, and Closed to the canonical Session contract", () => {
    expect(marginaliaExportSdkQuery(marginaliaExportStateFromSearchParams(new URLSearchParams())))
      .toEqual({ page: 1, pageSize: 20 });
    expect(marginaliaExportSdkQuery(marginaliaExportStateFromSearchParams(new URLSearchParams("status=active"))))
      .toEqual({ status: "active", page: 1, pageSize: 20 });
    expect(marginaliaExportSdkQuery(marginaliaExportStateFromSearchParams(new URLSearchParams("status=closed&q=notes&page=2"))))
      .toEqual({ q: "notes", status: "closed", page: 2, pageSize: 20 });
  });

  it("requests annotated candidates by default and all candidates when empty Sessions are included", () => {
    const state = marginaliaExportStateFromSearchParams(new URLSearchParams("status=closed&page=3"));
    expect(marginaliaExportCandidateQuery(state, false)).toEqual({
      status: "closed", page: 3, pageSize: 20, hasAnnotations: true,
    });
    expect(marginaliaExportCandidateQuery(state, true)).toEqual({
      status: "closed", page: 3, pageSize: 20,
    });
  });
});
