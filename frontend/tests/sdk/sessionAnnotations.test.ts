import { describe, expect, it } from "vitest";

import { createApiClient } from "../../packages/spl-api/src/client";
import { ApiError } from "../../packages/spl-api/src/errors";
import {
  closeMarginaliaSession,
  deleteMarginaliaSession,
  getMarginaliaSession,
  listMarginaliaSessionAnnotations,
  updateMarginaliaSession,
} from "../../packages/spl-api/src/marginalia";

const book = {
  id: "book-1", title: "Book", authors: [], series: null, cover_url: null, can_open: true,
  session_count: 1, active_session_count: 1, last_activity_at: "2026-07-30T12:00:00Z",
};
const detail = {
  id: "session-1", name: "Name", notes: " Note unchanged ", status: "active",
  started_at: "2026-07-01T12:00:00Z", closed_at: null,
  updated_at: "2026-07-30T11:00:00Z", last_activity_at: "2026-07-30T12:00:00Z",
  annotation_count: 2,
  progress: {
    location: " epubcfi(/6/8!/4/2) ",
    location_label: "Chapter 08 · 42% · The Blackstaff",
    updated_at: "2026-07-30T12:00:00Z",
  },
};
const envelope = { context: { book }, session: detail };
const annotations = [
  {
    id: "annotation-1", client_id: " client-highlight ", kind: "highlight",
    location: { location: " epubcfi(/6/8!/4/2) ", location_label: "Chapter 08 · 42%" },
    body: { text: " selected text ", prefix: " before ", suffix: " after ", color: "yellow", note: " note " },
    created_at: "2026-07-30T10:00:00Z", updated_at: "2026-07-30T11:00:00Z",
  },
  {
    id: "annotation-2", client_id: "bookmark-1", kind: "bookmark",
    location: { location: "epubcfi(/6/10!/4/2)", location_label: "Chapter 09 · 47%" },
    created_at: "2026-07-30T10:00:00Z", updated_at: "2026-07-30T11:00:00Z",
  },
] as const;

describe("Marginalia Product UI Session detail and close SDK", () => {
  it("adapts detail context and present progress without changing opaque strings", async () => {
    const calls: string[] = [];
    const client = { request: async <T>(path: string) => { calls.push(path); return envelope as T; } };
    const result = await getMarginaliaSession("session/id", client);
    expect(calls).toEqual(["/api/v1/marginalia/sessions/session%2Fid/"]);
    expect(result).toMatchObject({
      book: { id: "book-1", canOpen: true },
      session: {
        id: "session-1",
        notes: " Note unchanged ",
        progress: {
          location: " epubcfi(/6/8!/4/2) ",
          locationLabel: "Chapter 08 · 42% · The Blackstaff",
        },
      },
    });
    expect(result.session.progress).not.toHaveProperty("cfi");
  });

  it("PATCHes only supplied metadata and maps the returned detail envelope", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return envelope as T; } };
    await updateMarginaliaSession("session-1", { notes: " replacement " }, client);
    expect(calls[0]).toEqual({
      path: "/api/v1/marginalia/sessions/session-1/",
      init: {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ notes: " replacement " }),
      },
    });
  });

  it("DELETEs one encoded Session resource without a body and resolves 204 as void", async () => {
    const calls: Array<{ input: RequestInfo | URL; init?: RequestInit }> = [];
    const client = createApiClient(async (input, init) => {
      calls.push({ input, init });
      return new Response(null, { status: 204 });
    }, () => "csrf-token");

    const result = await deleteMarginaliaSession("session/id", client);

    expect(result).toBeUndefined();
    expect(calls).toHaveLength(1);
    expect(calls[0]?.input).toBe("/api/v1/marginalia/sessions/session%2Fid/");
    expect(calls[0]?.init?.method).toBe("DELETE");
    expect(calls[0]?.init?.body).toBeUndefined();
  });

  it("preserves the shared typed 404 error contract for Session deletion", async () => {
    const client = createApiClient(async () => new Response(
      JSON.stringify({ detail: "Not found." }),
      { status: 404, headers: { "Content-Type": "application/json" } },
    ));

    const error = await deleteMarginaliaSession("missing", client).catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({
      name: "ApiError",
      status: 404,
    });
  });

  it("POSTs optional final Product UI metadata and returns detail", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return envelope as T; } };
    await closeMarginaliaSession("session-1", {
      name: "Finished",
      notes: "Final note",
    }, client);
    expect(calls[0]?.path).toBe("/api/v1/marginalia/sessions/session-1/close/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      name: "Finished",
      notes: "Final note",
    });
  });
});

describe("Marginalia Annotation SDK", () => {
  it("maps the complete highlight/bookmark union and never adds a body to bookmarks", async () => {
    const calls: string[] = [];
    const client = { request: async <T>(path: string) => { calls.push(path); return { annotations } as T; } };
    const result = await listMarginaliaSessionAnnotations("session-1", client);
    expect(calls).toEqual(["/api/v1/marginalia/sessions/session-1/annotations/"]);
    expect(result[0]).toEqual({
      id: "annotation-1", clientId: " client-highlight ", kind: "highlight",
      location: { location: " epubcfi(/6/8!/4/2) ", locationLabel: "Chapter 08 · 42%" },
      body: { text: " selected text ", prefix: " before ", suffix: " after ", color: "yellow", note: " note " },
      createdAt: "2026-07-30T10:00:00Z", updatedAt: "2026-07-30T11:00:00Z",
    });
    expect(result[1]).toEqual({
      id: "annotation-2", clientId: "bookmark-1", kind: "bookmark",
      location: { location: "epubcfi(/6/10!/4/2)", locationLabel: "Chapter 09 · 47%" },
      createdAt: "2026-07-30T10:00:00Z", updatedAt: "2026-07-30T11:00:00Z",
    });
    expect(result[0]?.location).not.toHaveProperty("cfi");
    expect(result[1]).not.toHaveProperty("body");
  });

  it("preserves the Session-closed lifecycle conflict", async () => {
    const error = new ApiError("Closed.", 409, { code: "SESSION_CLOSED" });
    const client = { request: async <T>() => Promise.reject(error) as Promise<T> };

    await expect(closeMarginaliaSession("session-1", {}, client)).rejects.toBe(error);
  });
});
