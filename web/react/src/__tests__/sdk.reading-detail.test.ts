import { getReadingProgress, getReadingSession, listReadingAnnotations } from "@second-pass/spl-api";
import { describe, expect, it } from "vitest";

describe("reading detail SDK", () => {
  it("maps visible and unavailable Session Book projections without exposing locator fields", async () => {
    const calls: string[] = [];
    const visibleClient = { request: async <T>(path: string) => {
      calls.push(path);
      return {
        id: "session-1", book_id: "book-1", name: "Notes", status: "active", is_active: true,
        started_at: "2026-01-01T00:00:00Z", completed_at: null, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z",
        notes: "Session note", progression: 0.4, annotation_count: 2, can_open: true,
        book: { id: "book-1", title: "Visible Book", authors: [{ id: "author-1", name: "Author" }], series: { id: "series-1", name: "Series" }, series_index: "2.0", cover_url: "http://testserver/media/cover.jpg" },
      } as T;
    } };
    const visible = await getReadingSession("session/id", visibleClient);
    expect(calls).toEqual(["/api/v1/reading/sessions/session%2Fid/"]);
    expect(visible.book).toEqual({ id: "book-1", title: "Visible Book", authors: [{ id: "author-1", name: "Author" }], series: { id: "series-1", name: "Series" }, seriesIndex: "2.0", coverUrl: "/media/cover.jpg", unavailable: false });

    const hiddenClient = { request: async <T>() => ({
      id: "session-2", book_id: "hidden-book", name: "", status: "completed", is_active: false,
      started_at: "2026-01-01T00:00:00Z", completed_at: "2026-01-03T00:00:00Z", created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-03T00:00:00Z",
      notes: "", progression: null, annotation_count: 0, can_open: false,
      book: { id: "hidden-book", title: "", authors: [], series: null, series_index: null, cover_url: null },
    }) as T };
    const hidden = await getReadingSession("session-2", hiddenClient);
    expect(hidden.book).toEqual({ id: null, title: "", authors: [], series: null, seriesIndex: null, coverUrl: null, unavailable: true });
  });

  it("maps progress while dropping current-location internals", async () => {
    const client = { request: async <T>() => ({ session: "session-1", current_location: { cfi: "epubcfi(/6/2)" }, progression: 0.75, profile_version: "1.0", created_at: null, updated_at: "2026-01-02T00:00:00Z" }) as T };
    const progress = await getReadingProgress("session-1", client);
    expect(progress).toEqual({ sessionId: "session-1", progression: 0.75, createdAt: null, updatedAt: "2026-01-02T00:00:00Z" });
    expect(progress).not.toHaveProperty("currentLocation");
  });

  it("serializes annotation filters and maps content without selector or quote internals", async () => {
    const calls: string[] = [];
    const client = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 2, next: null, previous: null, results: [
        { id: "annotation-1", kind: "highlight", selector: { kind: "epub_cfi", value: "epubcfi(/6/2)" }, quote: { prefix: "before" }, highlight_text: "Quoted text", highlight_color: "yellow", comment_text: "Comment", has_comment: true, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-02T00:00:00Z" },
        { id: "annotation-2", kind: "bookmark", selector: { kind: "epub_cfi", value: "epubcfi(/6/4)" }, quote: {}, highlight_text: "", highlight_color: "", comment_text: "", has_comment: false, created_at: "2026-01-03T00:00:00Z", updated_at: "2026-01-03T00:00:00Z" },
      ] } as T;
    } };
    const page = await listReadingAnnotations({ sessionId: "session/id", kind: "highlight", ordering: "created", page: 2, pageSize: 30 }, client);
    expect(calls).toEqual(["/api/v1/reading/annotations/?session_id=session%2Fid&kind=highlight&ordering=created&page=2&page_size=30"]);
    expect(page.items[0]).toMatchObject({ kind: "highlight", highlightText: "Quoted text", commentText: "Comment", hasComment: true });
    expect(page.items[1]).toMatchObject({ kind: "bookmark", highlightText: "", commentText: "" });
    expect(page.items[0]).not.toHaveProperty("selector");
    expect(page.items[0]).not.toHaveProperty("quote");
  });

  it("preserves structured SDK errors", async () => {
    const error = new Error("structured");
    const client = { request: async <T>() => Promise.reject(error) as Promise<T> };
    await expect(getReadingSession("missing", client)).rejects.toBe(error);
    await expect(getReadingProgress("missing", client)).rejects.toBe(error);
    await expect(listReadingAnnotations({ sessionId: "missing" }, client)).rejects.toBe(error);
  });
});
