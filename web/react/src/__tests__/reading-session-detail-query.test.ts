import { describe, expect, it } from "vitest";

import { readingAnnotationsSdkQuery, readingSessionDetailSearchParams, readingSessionDetailStateFromSearchParams, withReadingSessionDetailChange } from "../features/reading/readingSessionDetailQuery";

describe("reading Session Detail query", () => {
  it("canonicalizes unsupported values and omits defaults", () => {
    const state = readingSessionDetailStateFromSearchParams(new URLSearchParams("kind=comment&order=sideways&page=0&page_size=200"));
    expect(state).toEqual({ filter: "all", order: "newest", page: 1, pageSize: 20 });
    expect(readingSessionDetailSearchParams(state).toString()).toBe("");
  });

  it("maps supported filter, ordering, and paging state to the SDK", () => {
    const state = readingSessionDetailStateFromSearchParams(new URLSearchParams("kind=bookmark&order=oldest&page=3&page_size=40"));
    expect(readingAnnotationsSdkQuery("session-1", state)).toEqual({ sessionId: "session-1", kind: "bookmark", ordering: "created", page: 3, pageSize: 40 });
    expect(readingSessionDetailSearchParams(state).toString()).toBe("kind=bookmark&order=oldest&page=3&page_size=40");
    expect(withReadingSessionDetailChange(state, { filter: "highlight" })).toMatchObject({ filter: "highlight", page: 1 });
  });
});
