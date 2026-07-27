import { describe, expect, it } from "vitest";

import type { ApiClient } from "../client";
import { ApiError } from "../errors";
import { listRecentReadingSessions } from "../reading";

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
