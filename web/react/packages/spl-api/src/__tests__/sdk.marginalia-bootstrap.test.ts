import { describe, expect, it } from "vitest";

import {
  getActiveMarginaliaSession,
  openMarginaliaBook,
  startOverMarginaliaBook,
} from "../marginalia";

const book = {
  id: "book-1", title: "Book", authors: [], series: null, cover_url: null, can_open: true,
  session_count: 2, active_session_count: 1, last_activity_at: "2026-07-30T12:00:00Z",
};
const session = {
  id: "session-1", name: "", notes: "", status: "active",
  started_at: "2026-07-30T12:00:00Z", closed_at: null, updated_at: "2026-07-30T12:00:00Z",
  last_activity_at: "2026-07-30T12:00:00Z", annotation_count: 0, progress: null,
};
const closed = { ...session, id: "session-closed", status: "closed", closed_at: "2026-07-29T12:00:00Z" };
const annotation = {
  id: "bookmark-1", client_id: "client-bookmark", kind: "bookmark",
  location: { cfi: "epubcfi(/6/2)", location_label: "Location 001" },
  created_at: "2026-07-30T12:00:00Z", updated_at: "2026-07-30T12:00:00Z",
};

function bootstrap(overrides: Record<string, unknown> = {}) {
  return {
    created: true,
    context: { book },
    session,
    annotations: [annotation],
    closed_sessions: {
      count: 1,
      next: "http://testserver/api/v1/marginalia/books/book-1/sessions/?status=closed&page=2",
      previous: null,
      results: [closed],
    },
    ...overrides,
  };
}

describe("Marginalia lifecycle bootstrap SDK", () => {
  it("POSTs open creation defaults and maps the complete bootstrap", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return bootstrap() as T; } };
    const result = await openMarginaliaBook("book/id", { name: " New ", notes: " Notes " }, client);
    expect(calls[0]).toEqual({
      path: "/api/v1/marginalia/books/book%2Fid/open/",
      init: { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: " New ", notes: " Notes " }) },
    });
    expect(result.created).toBe(true);
    expect(result.session.id).toBe("session-1");
    expect(result.annotations[0]).toMatchObject({ kind: "bookmark", clientId: "client-bookmark" });
    expect(result.closedSessions).toMatchObject({ count: 1, items: [{ id: "session-closed", status: "closed" }] });
  });

  it("maps active-session with no active Session and retains closed history", async () => {
    const calls: string[] = [];
    const client = { request: async <T>(path: string) => { calls.push(path); return bootstrap({ created: false, session: null, annotations: [] }) as T; } };
    const result = await getActiveMarginaliaSession("book-1", client);
    expect(calls).toEqual(["/api/v1/marginalia/books/book-1/active-session/"]);
    expect(result.session).toBeNull();
    expect(result.annotations).toEqual([]);
    expect(result.closedSessions.count).toBe(1);
  });

  it("POSTs finalization with mandatory Idempotency-Key outside the JSON body", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return bootstrap() as T; } };
    await startOverMarginaliaBook(
      "book-1",
      { name: "Finished", notes: "Done", progress: { cfi: " cfi ", locationLabel: " Label " } },
      "retry-key-1",
      client,
    );
    expect(calls[0]?.path).toBe("/api/v1/marginalia/books/book-1/start-over/");
    expect(calls[0]?.init?.headers).toEqual({
      "Content-Type": "application/json",
      "Idempotency-Key": "retry-key-1",
    });
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      name: "Finished",
      notes: "Done",
      progress: { cfi: " cfi ", location_label: " Label " },
    });
  });
});
