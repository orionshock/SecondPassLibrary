import { describe, expect, it } from "vitest";

import { ApiError, uploadLibraryImport } from "@second-pass/spl-api";
import type { ApiClient } from "../../packages/spl-api/src/client";

describe("imports SDK", () => {
  it("posts one multipart file and maps every result item", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const items = Array.from({ length: 55 }, (_, index) => ({
      status: index === 0 ? "imported" as const : "duplicate" as const,
      source_label: `book-${index}.epub`, safe_message: index === 0 ? "Imported." : "Already exists.",
      error_category: index === 0 ? "" : "checksum_duplicate",
      book_id: `internal-${index}`,
      ...(index === 0 ? { title: "Readable title", authors: ["First Author", "Second Author"], series: "Series Name", series_index: "1.00" } : {}),
    }));
    const response = {
      source_type: "zip", source_label: "library.zip",
      counts: { imported: 1, duplicate: 54, conflict: 0, failed: 0, skipped: 0 }, items,
    };
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => { calls.push({ path, init }); return response as T; } };
    const file = new File(["epub"], "library.zip", { type: "application/zip" });

    const result = await uploadLibraryImport(file, client);

    expect(calls).toHaveLength(1);
    expect(calls[0]?.path).toBe("/api/v1/library/imports/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(calls[0]?.init?.body).toBeInstanceOf(FormData);
    expect(Array.from((calls[0]?.init?.body as FormData).entries())).toEqual([["file", file]]);
    expect(new Headers(calls[0]?.init?.headers).has("Content-Type")).toBe(false);
    expect(result.counts).toEqual(response.counts);
    expect(result.items).toHaveLength(55);
    expect(result.items[0]).toEqual({
      status: "imported", sourceLabel: "book-0.epub", safeMessage: "Imported.", errorCategory: "", bookId: "internal-0",
      title: "Readable title", authors: ["First Author", "Second Author"], series: "Series Name", seriesIndex: "1.00",
    });
  });

  it("preserves detailed safe failure fields and normalized upload errors", async () => {
    const response = {
      source_type: "epub", source_label: "broken.epub",
      counts: { imported: 0, duplicate: 0, conflict: 0, failed: 1, skipped: 0 },
      items: [{
        status: "failed" as const,
        source_label: "broken.epub",
        safe_message: "The EPUB package is invalid.",
        error_category: "invalid_candidate",
      }],
    };
    const client: ApiClient = { request: async <T>() => response as T };
    const result = await uploadLibraryImport(new File(["bad"], "broken.epub"), client);
    expect(result.items[0]).toEqual({
      status: "failed",
      sourceLabel: "broken.epub",
      safeMessage: "The EPUB package is invalid.",
      errorCategory: "invalid_candidate",
    });

    const error = new ApiError("Invalid upload.", 400, { fields: { file: ["Only .epub and .zip uploads are supported."] } });
    const failingClient: ApiClient = { request: async <T>() => Promise.reject(error) as Promise<T> };
    await expect(uploadLibraryImport(new File(["bad"], "notes.txt"), failingClient)).rejects.toBe(error);
  });
});
