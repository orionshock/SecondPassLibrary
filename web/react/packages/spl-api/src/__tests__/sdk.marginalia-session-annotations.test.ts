import { describe, expect, it } from "vitest";

import { ApiError } from "../errors";
import {
  closeMarginaliaSession,
  getMarginaliaProgress,
  getMarginaliaSession,
  listMarginaliaSessionAnnotations,
  replaceMarginaliaProgress,
  syncMarginaliaSessionAnnotations,
  updateMarginaliaSession,
  type MarginaliaAnnotationOperation,
} from "../marginalia";

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
    cfi: " epubcfi(/6/8!/4/2) ",
    location_label: "Chapter 08 · 42% · The Blackstaff",
    updated_at: "2026-07-30T12:00:00Z",
  },
};
const envelope = { context: { book }, session: detail };
const annotations = [
  {
    id: "annotation-1", client_id: " client-highlight ", kind: "highlight",
    location: { cfi: " epubcfi(/6/8!/4/2) ", location_label: "Chapter 08 · 42%" },
    body: { text: " selected text ", prefix: " before ", suffix: " after ", color: "yellow", note: " note " },
    created_at: "2026-07-30T10:00:00Z", updated_at: "2026-07-30T11:00:00Z",
  },
  {
    id: "annotation-2", client_id: "bookmark-1", kind: "bookmark",
    location: { cfi: "epubcfi(/6/10!/4/2)", location_label: "Chapter 09 · 47%" },
    created_at: "2026-07-30T10:00:00Z", updated_at: "2026-07-30T11:00:00Z",
  },
] as const;

describe("Marginalia Session detail, progress, and close SDK", () => {
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
          cfi: " epubcfi(/6/8!/4/2) ",
          locationLabel: "Chapter 08 · 42% · The Blackstaff",
        },
      },
    });
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

  it("maps null progress and atomically PUTs a complete progress location", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    let response: unknown = { progress: null };
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return response as T; } };
    await expect(getMarginaliaProgress("session-1", client)).resolves.toBeNull();
    response = { progress: detail.progress };
    await expect(replaceMarginaliaProgress("session-1", {
      cfi: " epubcfi(/6/8!/4/2) ",
      locationLabel: "Chapter 08 · 42% · The Blackstaff",
    }, client)).resolves.toMatchObject({ locationLabel: "Chapter 08 · 42% · The Blackstaff" });
    expect(calls[1]?.init).toEqual({
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cfi: " epubcfi(/6/8!/4/2) ",
        location_label: "Chapter 08 · 42% · The Blackstaff",
      }),
    });
  });

  it("POSTs optional final metadata/progress and returns detail", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return envelope as T; } };
    await closeMarginaliaSession("session-1", {
      name: "Finished",
      progress: { cfi: "epubcfi(/6/42)", locationLabel: "Chapter 42 · 100%" },
    }, client);
    expect(calls[0]?.path).toBe("/api/v1/marginalia/sessions/session-1/close/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      name: "Finished",
      progress: { cfi: "epubcfi(/6/42)", location_label: "Chapter 42 · 100%" },
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
      location: { cfi: " epubcfi(/6/8!/4/2) ", locationLabel: "Chapter 08 · 42%" },
      body: { text: " selected text ", prefix: " before ", suffix: " after ", color: "yellow", note: " note " },
      createdAt: "2026-07-30T10:00:00Z", updatedAt: "2026-07-30T11:00:00Z",
    });
    expect(result[1]).toEqual({
      id: "annotation-2", clientId: "bookmark-1", kind: "bookmark",
      location: { cfi: "epubcfi(/6/10!/4/2)", locationLabel: "Chapter 09 · 47%" },
      createdAt: "2026-07-30T10:00:00Z", updatedAt: "2026-07-30T11:00:00Z",
    });
    expect(result[1]).not.toHaveProperty("body");
  });

  it("maps typed batch upsert/delete operations and returns authoritative state", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return { annotations } as T; } };
    const operations: MarginaliaAnnotationOperation[] = [
      {
        action: "upsert",
        annotation: {
          clientId: " client-highlight ", kind: "highlight",
          location: { cfi: " cfi ", locationLabel: " Label " },
          body: { text: " selected text ", prefix: " before ", note: " note " },
        },
      },
      { action: "upsert", annotation: { clientId: "bookmark-1", kind: "bookmark", location: { cfi: "bookmark-cfi" } } },
      { action: "delete", clientId: "deleted-1" },
    ];
    const result = await syncMarginaliaSessionAnnotations("session/id", operations, client);
    expect(calls[0]?.path).toBe("/api/v1/marginalia/sessions/session%2Fid/annotations/batch/");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ operations: [
      { action: "upsert", annotation: { client_id: " client-highlight ", kind: "highlight", location: { cfi: " cfi ", location_label: " Label " }, body: { text: " selected text ", prefix: " before ", note: " note " } } },
      { action: "upsert", annotation: { client_id: "bookmark-1", kind: "bookmark", location: { cfi: "bookmark-cfi" } } },
      { action: "delete", client_id: "deleted-1" },
    ] });
    expect(result).toHaveLength(2);
  });

  it("preserves representative normalized API errors", async () => {
    for (const error of [
      new ApiError("Invalid.", 400, { code: "INVALID_REQUEST" }),
      new ApiError("Missing.", 404),
      new ApiError("Closed.", 409, { code: "SESSION_CLOSED" }),
    ]) {
      const client = { request: async <T>() => Promise.reject(error) as Promise<T> };
      await expect(syncMarginaliaSessionAnnotations("session-1", [], client)).rejects.toBe(error);
    }
  });
});
