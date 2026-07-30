import { describe, expect, it } from "vitest";

import type { ApiClient } from "../client";
import { ApiError } from "../errors";
import {
  getMarginaliaBook,
  listMarginaliaBooks,
  listMarginaliaBookSessions,
  listMarginaliaSessions,
  listRecentMarginaliaSessions,
} from "../marginalia";

const book = {
  id: "book-1",
  title: "The Book",
  authors: [{ id: "author-1", name: "The Author" }],
  series: { id: "series-1", name: "The Series", series_index: "2.5" },
  cover_url: "http://testserver/media/covers/book.jpg?size=small",
  can_open: false,
  session_count: 3,
  active_session_count: 1,
  last_activity_at: "2026-07-30T12:00:00Z",
};

const session = {
  id: "session-1",
  name: "Second pass",
  notes: "  Exact session notes.\n",
  status: "closed",
  started_at: "2026-07-01T12:00:00Z",
  closed_at: "2026-07-20T12:00:00Z",
  updated_at: "2026-07-20T12:00:00Z",
  last_activity_at: "2026-07-21T12:00:00Z",
  annotation_count: 12,
} as const;

describe("Marginalia Book SDK", () => {
  it("maps Book pagination, search, Series, counts, dates, and cover URLs", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: "http://testserver/api/v1/marginalia/books/?page=2", previous: null, results: [book] } as T;
    } };

    const page = await listMarginaliaBooks({ q: "author notes", page: 2, pageSize: 40 }, client);

    expect(calls).toEqual(["/api/v1/marginalia/books/?q=author+notes&page=2&page_size=40"]);
    expect(page).toEqual({
      count: 1,
      next: "http://testserver/api/v1/marginalia/books/?page=2",
      previous: null,
      items: [{
        id: "book-1",
        title: "The Book",
        authors: [{ id: "author-1", name: "The Author" }],
        series: { id: "series-1", name: "The Series", seriesIndex: "2.5" },
        coverUrl: "/media/covers/book.jpg?size=small",
        canOpen: false,
        sessionCount: 3,
        activeSessionCount: 1,
        lastActivityAt: "2026-07-30T12:00:00Z",
      }],
    });
  });

  it("uses the encoded Book detail path", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => { calls.push(path); return book as T; } };
    await getMarginaliaBook("book/id", client);
    expect(calls).toEqual(["/api/v1/marginalia/books/book%2Fid/"]);
  });
});

describe("Marginalia Session list SDK", () => {
  it("maps nested Session pagination and its canonical parent Book context", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { count: 1, next: null, previous: null, context: { book }, results: [session] } as T;
    } };

    const page = await listMarginaliaBookSessions(
      "book/id",
      { q: "  exact text ", status: "closed", page: 3, pageSize: 20 },
      client,
    );

    expect(calls).toEqual([
      "/api/v1/marginalia/books/book%2Fid/sessions/?q=++exact+text+&page=3&page_size=20&status=closed",
    ]);
    expect(page.book.title).toBe("The Book");
    expect(page.items).toEqual([{
      id: "session-1",
      name: "Second pass",
      notes: "  Exact session notes.\n",
      status: "closed",
      startedAt: "2026-07-01T12:00:00Z",
      closedAt: "2026-07-20T12:00:00Z",
      updatedAt: "2026-07-20T12:00:00Z",
      lastActivityAt: "2026-07-21T12:00:00Z",
      annotationCount: 12,
    }]);
  });

  it("maps only the bounded Book reference on global Session rows", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return {
        count: 1,
        next: null,
        previous: null,
        results: [{
          ...session,
          book: {
            id: "book-1",
            title: "The Book",
            cover_url: "http://testserver/media/covers/book.jpg",
            can_open: false,
          },
        }],
      } as T;
    } };

    const page = await listMarginaliaSessions({ status: "active" }, client);

    expect(calls).toEqual(["/api/v1/marginalia/sessions/?status=active"]);
    expect(page.items[0]?.book).toEqual({
      id: "book-1",
      title: "The Book",
      coverUrl: "/media/covers/book.jpg",
      canOpen: false,
    });
    expect(page.items[0]?.book).not.toHaveProperty("authors");
    expect(page.items[0]?.book).not.toHaveProperty("sessionCount");
  });
});

describe("Marginalia recent Session SDK", () => {
  it("maps the bounded Dashboard projection and defaults to active-only", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return {
        results: [{
          id: "session-1",
          name: "Current pass",
          status: "active",
          last_activity_at: "2026-07-30T12:00:00Z",
          book: {
            id: "book-1",
            title: "Remembered Book",
            cover_url: "http://testserver/media/covers/book.jpg",
            can_open: false,
          },
        }],
      } as T;
    } };

    const results = await listRecentMarginaliaSessions({}, client);

    expect(calls).toEqual(["/api/v1/marginalia/sessions/recent/"]);
    expect(results).toEqual([{
      id: "session-1",
      name: "Current pass",
      status: "active",
      lastActivityAt: "2026-07-30T12:00:00Z",
      book: {
        id: "book-1",
        title: "Remembered Book",
        coverUrl: "/media/covers/book.jpg",
        canOpen: false,
      },
    }]);
  });

  it("maps the optional limit and closed inclusion query", async () => {
    const calls: string[] = [];
    const client: ApiClient = { request: async <T>(path: string) => {
      calls.push(path);
      return { results: [] } as T;
    } };

    await listRecentMarginaliaSessions({ limit: 10, includeClosed: true }, client);

    expect(calls).toEqual([
      "/api/v1/marginalia/sessions/recent/?limit=10&include_closed=true",
    ]);
  });

  it("preserves the central SDK error abstraction", async () => {
    const error = new ApiError("Unavailable.", 409, { code: "INVALID_REQUEST" });
    const client: ApiClient = {
      request: async <T>() => Promise.reject(error) as Promise<T>,
    };

    await expect(listRecentMarginaliaSessions({}, client)).rejects.toBe(error);
  });
});
