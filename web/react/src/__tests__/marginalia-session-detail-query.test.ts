import { describe, expect, it } from "vitest";

import { defaultMarginaliaAnnotationCategories, marginaliaAnnotationsSdkQuery, marginaliaSessionDetailSearchParams, marginaliaSessionDetailStateFromSearchParams, withMarginaliaSessionDetailChange } from "../features/marginalia/marginaliaSessionDetailQuery";

describe("Marginalia Session Detail query", () => {
  it("canonicalizes unsupported values and omits defaults", () => {
    const state = marginaliaSessionDetailStateFromSearchParams(new URLSearchParams("show=comment&order=sideways&page=0&page_size=200"));
    expect(state).toEqual({ categories: defaultMarginaliaAnnotationCategories, order: "newest", page: 1, pageSize: 20 });
    expect(marginaliaSessionDetailSearchParams(state).toString()).toBe("");
    expect(marginaliaAnnotationsSdkQuery("session-1", state)).toEqual({ sessionId: "session-1", categories: ["highlight", "highlightWithNote"], ordering: "-created", page: 1, pageSize: 20 });
  });

  it("maps repeated category selections and paging state to the SDK", () => {
    const bookmarkOnly = marginaliaSessionDetailStateFromSearchParams(new URLSearchParams("show=bookmark"));
    expect(marginaliaAnnotationsSdkQuery("session-1", bookmarkOnly).categories).toEqual(["bookmark"]);
    const notedHighlightsOnly = marginaliaSessionDetailStateFromSearchParams(new URLSearchParams("show=highlight-with-note"));
    expect(marginaliaAnnotationsSdkQuery("session-1", notedHighlightsOnly).categories).toEqual(["highlightWithNote"]);

    const state = marginaliaSessionDetailStateFromSearchParams(new URLSearchParams("show=bookmark&show=highlight-with-note&order=oldest&page=3&page_size=40"));
    expect(marginaliaAnnotationsSdkQuery("session-1", state)).toEqual({ sessionId: "session-1", categories: ["bookmark", "highlightWithNote"], ordering: "created", page: 3, pageSize: 40 });
    expect(marginaliaSessionDetailSearchParams(state).toString()).toBe("show=bookmark&show=highlight-with-note&order=oldest&page=3&page_size=40");
    expect(withMarginaliaSessionDetailChange(state, { categories: ["highlight"] })).toMatchObject({ categories: ["highlight"], page: 1 });
  });

  it("maps every supported time ordering and resets paging when ordering changes", () => {
    const expected = {
      newest: "-created",
      oldest: "created",
      "recently-edited": "-modified",
      "oldest-edited": "modified",
    } as const;
    for (const [order, ordering] of Object.entries(expected)) {
      const state = marginaliaSessionDetailStateFromSearchParams(new URLSearchParams(`order=${order}&page=4`));
      expect(marginaliaAnnotationsSdkQuery("session-1", state).ordering).toBe(ordering);
      expect(withMarginaliaSessionDetailChange(state, { order: "newest" })).toMatchObject({ page: 1 });
    }
  });
});
