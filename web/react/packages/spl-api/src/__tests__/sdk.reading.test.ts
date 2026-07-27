import { describe, expect, it } from "vitest";

import type { ApiClient } from "../client";
import { ApiError } from "../errors";
import { applyReadingImport, listReadingSessions, listRecentReadingSessions, previewReadingImport } from "../reading";

const response = {
  count: 2,
  results: [
    {
      last_activity_at: "2026-07-27T18:30:00Z",
      session: {
        id: "session-1",
        name: "Evening read",
        status: "active",
        is_active: true,
        progression: 0.42,
      },
      book: {
        id: "book-1",
        title: "A Book",
        cover_url: "http://testserver/media/covers/a.jpg?size=small",
      },
    },
    {
      last_activity_at: "2026-07-26T12:00:00Z",
      session: {
        id: "session-2",
        name: "",
        status: "active",
        is_active: true,
        progression: null,
      },
      book: { id: "book-2", title: "No Cover", cover_url: null },
    },
  ],
};

describe("recent reading sessions", () => {
  it("uses the unpaginated recent-sessions path by default and maps the response", async () => {
    const calls: string[] = [];
    const client: ApiClient = {
      request: async <T>(path: string) => {
        calls.push(path);
        return response as T;
      },
    };

    await expect(listRecentReadingSessions({}, client)).resolves.toEqual([
      {
        lastActivityAt: "2026-07-27T18:30:00Z",
        session: {
          id: "session-1",
          name: "Evening read",
          status: "active",
          isActive: true,
          progression: 0.42,
        },
        book: {
          id: "book-1",
          title: "A Book",
          coverUrl: "/media/covers/a.jpg?size=small",
        },
      },
      {
        lastActivityAt: "2026-07-26T12:00:00Z",
        session: {
          id: "session-2",
          name: "",
          status: "active",
          isActive: true,
          progression: null,
        },
        book: { id: "book-2", title: "No Cover", coverUrl: null },
      },
    ]);
    expect(calls).toEqual(["/api/v1/reading/sessions/recent/"]);
  });

  it("serializes an explicit limit", async () => {
    const calls: string[] = [];
    const client: ApiClient = {
      request: async <T>(path: string) => {
        calls.push(path);
        return { count: 0, results: [] } as T;
      },
    };

    await listRecentReadingSessions({ limit: 10 }, client);
    expect(calls).toEqual(["/api/v1/reading/sessions/recent/?limit=10"]);
  });

  it("preserves normalized SDK errors", async () => {
    const error = new ApiError("Recent reading is unavailable.", 503, { code: "READING_UNAVAILABLE" });
    const client: ApiClient = { request: async () => Promise.reject(error) };
    await expect(listRecentReadingSessions({}, client)).rejects.toBe(error);
  });
});

describe("reading session list", () => {
  const pageResponse = {
    count: 2,
    next: "http://testserver/api/v1/reading/sessions/?page=2",
    previous: null,
    results: [
      {
        id: "session-visible",
        book_id: "book-visible",
        name: "Morning notes",
        status: "active",
        is_active: true,
        started_at: "2026-07-20T12:00:00Z",
        completed_at: null,
        created_at: "2026-07-20T12:00:00Z",
        updated_at: "2026-07-21T12:00:00Z",
        notes: "Remember this chapter.",
        progression: 0.375,
        annotation_count: 3,
        filtered_book_session_count: 1,
        can_open: true,
        book: {
          id: "book-visible",
          title: "Visible Book",
          authors: [],
          series: null,
          series_index: null,
          cover_url: "http://testserver/media/covers/visible.jpg?size=small",
        },
      },
      {
        id: "session-hidden",
        book_id: "book-hidden",
        name: "",
        status: "completed",
        is_active: false,
        started_at: "2026-06-01T12:00:00Z",
        completed_at: "2026-06-02T12:00:00Z",
        created_at: "2026-06-01T12:00:00Z",
        updated_at: "2026-06-02T12:00:00Z",
        notes: "Owned notes remain available.",
        progression: null,
        annotation_count: 0,
        filtered_book_session_count: 1,
        can_open: false,
        book: {
          id: "book-hidden",
          title: "",
          authors: [],
          series: null,
          series_index: null,
          cover_url: null,
        },
      },
    ],
  };

  it("uses the default list path and maps visible and unavailable Book projections", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return pageResponse as T; } };
    const page = await listReadingSessions({}, client);

    expect(calls).toEqual(["/api/v1/reading/sessions/"]);
    expect(page).toEqual({
      count: 2,
      next: "http://testserver/api/v1/reading/sessions/?page=2",
      previous: null,
      items: [
        {
          id: "session-visible", bookId: "book-visible", name: "Morning notes", status: "active", isActive: true,
          startedAt: "2026-07-20T12:00:00Z", completedAt: null, updatedAt: "2026-07-21T12:00:00Z",
          notes: "Remember this chapter.", progression: 0.375, annotationCount: 3, canOpen: true,
          book: { id: "book-visible", title: "Visible Book", coverUrl: "/media/covers/visible.jpg?size=small", unavailable: false },
        },
        {
          id: "session-hidden", bookId: "book-hidden", name: "", status: "completed", isActive: false,
          startedAt: "2026-06-01T12:00:00Z", completedAt: "2026-06-02T12:00:00Z", updatedAt: "2026-06-02T12:00:00Z",
          notes: "Owned notes remain available.", progression: null, annotationCount: 0, canOpen: false,
          book: { id: "book-hidden", title: "", coverUrl: null, unavailable: true },
        },
      ],
    });
  });

  it("serializes supported filters and pagination without inventing defaults", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return { count: 0, next: null, previous: null, results: [] } as T; } };
    await listReadingSessions({ q: "storm notes", isActive: false, status: "archived", page: 3, pageSize: 40 }, client);
    expect(calls).toEqual(["/api/v1/reading/sessions/?q=storm+notes&is_active=false&status=archived&page=3&page_size=40"]);
  });

  it("preserves structured SDK errors", async () => {
    const error = new ApiError("Reading history is unavailable.", 503, { code: "READING_UNAVAILABLE" });
    const client: ApiClient = { request: async () => Promise.reject(error) };
    await expect(listReadingSessions({}, client)).rejects.toBe(error);
  });
});

describe("marginalia import", () => {
  const previewResponse = {
    valid: true,
    import_token: "opaque-preview-token",
    can_apply: true,
    summary: { books: 2, sessions: 2, annotations: 3 },
    warnings: ["Active exported sessions will be imported as historical sessions."],
    unmatched_entries: 1,
    unmatched_download_url: "/api/v1/reading/import/unmatched/?import_token=opaque-preview-token",
    books: [
      {
        title: "Matched Book", authors: ["Author One"], source: "book:source", file_hash: "sha256:hidden",
        session_count: 1, annotation_count: 3, match: { status: "matched", book_title: "Local Book" },
        cover_url: "http://testserver/media/covers/matched.jpg", will_import: true, warning: "",
        sessions: [{
          export_session_id: "export-session-1", name: "Imported session", notes: "Notes", status: "active",
          started_at: "2026-01-01T00:00:00Z", completed_at: null, annotation_count: 3, bookmark_count: 1,
          highlight_count: 2, commented_highlight_count: 1, will_import: true, needs_reader: false,
          active_will_import_as_historical: true, possible_duplicate: false, warning: "",
        }],
      },
      {
        title: "Missing Book", authors: [], source: "book:missing", file_hash: "sha256:missing",
        session_count: 1, annotation_count: 0, match: { status: "unmatched", book_title: null },
        cover_url: "", will_import: false, warning: "No visible local book matched.",
        sessions: [{
          export_session_id: "export-session-2", name: "", notes: "", status: "completed",
          started_at: null, completed_at: null, annotation_count: 0, bookmark_count: 0,
          highlight_count: 0, commented_highlight_count: 0, will_import: false, needs_reader: false,
          active_will_import_as_historical: false, possible_duplicate: false, warning: "",
        }],
      },
    ],
  };

  it("posts the preview file as the exact multipart contract and maps review data", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return previewResponse as T; } };
    const file = new File(["{}"], "marginalia.json", { type: "application/json" });
    const preview = await previewReadingImport(file, client);

    expect(calls[0]?.path).toBe("/api/v1/reading/import/preview/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(Array.from((calls[0]?.init?.body as FormData).entries())).toEqual([["file", file]]);
    expect(preview).toMatchObject({
      importToken: "opaque-preview-token", canApply: true, summary: { books: 2, sessions: 2, annotations: 3 },
      unmatchedEntries: 1, unmatchedDownloadAvailable: true,
      books: [
        { title: "Matched Book", authors: ["Author One"], matchStatus: "matched", matchedBookTitle: "Local Book", coverUrl: "/media/covers/matched.jpg", sessions: [{ exportSessionId: "export-session-1", willImport: true, activeWillImportAsHistorical: true }] },
        { title: "Missing Book", matchStatus: "unmatched", matchedBookTitle: null, coverUrl: null, sessions: [{ exportSessionId: "export-session-2", willImport: false }] },
      ],
    });
  });

  it("posts the opaque token and exact selected Session edits, then maps result counts", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return { applied: true, summary: { books_matched: 1, books_skipped: 0, sessions_created: 1, annotations_created: 3, bookmarks_created: 1, highlights_created: 2, commented_highlights_created: 1 }, warnings: [] } as T;
    } };
    const result = await applyReadingImport({ importToken: "opaque-preview-token", books: [{ selectionReference: { source: "book:source", fileHash: "sha256:hidden", title: "Matched Book" }, sessions: [{ exportSessionId: "export-session-1", name: "Edited name", notes: "Edited notes" }] }] }, client);
    const entries = Array.from((calls[0]?.init?.body as FormData).entries());
    expect(calls[0]?.path).toBe("/api/v1/reading/import/apply/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(entries[0]).toEqual(["import_token", "opaque-preview-token"]);
    expect(JSON.parse(String(entries[1]?.[1]))).toEqual({ books: [{ source: "book:source", sessions: [{ export_session_id: "export-session-1", selected: true, name: "Edited name", notes: "Edited notes" }] }] });
    expect(result.summary).toEqual({ booksMatched: 1, booksSkipped: 0, sessionsCreated: 1, annotationsCreated: 3, bookmarksCreated: 1, highlightsCreated: 2, commentedHighlightsCreated: 1 });
  });

  it("preserves preview and apply SDK errors", async () => {
    const error = new ApiError("The server could not complete the request.", 400, { fields: { importToken: ["Import preview expired."] } });
    const client: ApiClient = { request: async () => Promise.reject(error) };
    await expect(previewReadingImport(new File(["{}"], "bad.json"), client)).rejects.toBe(error);
    await expect(applyReadingImport({ importToken: "expired", books: [] }, client)).rejects.toBe(error);
  });
});
