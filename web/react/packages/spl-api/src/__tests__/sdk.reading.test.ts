import { describe, expect, it } from "vitest";

import type { ApiClient } from "../client";
import { ApiError } from "../errors";
import { listReadingSessions, listRecentReadingSessions } from "../reading";

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
    await listReadingSessions({ q: "storm notes", isActive: false, status: "archived", page: 3, pageSize: 40, hasAnnotations: true }, client);
    expect(calls).toEqual(["/api/v1/reading/sessions/?q=storm+notes&is_active=false&status=archived&page=3&page_size=40&has_annotations=true"]);
  });

  it("preserves structured SDK errors", async () => {
    const error = new ApiError("Reading history is unavailable.", 503, { code: "READING_UNAVAILABLE" });
    const client: ApiClient = { request: async () => Promise.reject(error) };
    await expect(listReadingSessions({}, client)).rejects.toBe(error);
  });
});
