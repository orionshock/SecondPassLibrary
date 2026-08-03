import { describe, expect, it, vi } from "vitest";

import type { ApiClient, AttachmentApiClient, AttachmentDownload } from "../client";
import { ApiError } from "../errors";
import {
  applyMarginaliaImport,
  downloadUnmatchedMarginaliaImport,
  previewMarginaliaImport,
} from "../marginaliaImport";

const previewResponse = {
  import_token: "opaque-preview-token",
  include_empty_sessions: true,
  can_apply: true,
  summary: { book_count: 2, reading_session_count: 2, annotation_count: 3 },
  matched_book_count: 1,
  unmatched_book_count: 1,
  unmatched_reading_session_count: 1,
  unmatched_downloadable_reading_session_count: 1,
  warnings: [{ code: "POSSIBLE_DUPLICATE_SESSION", message: "Possible duplicate.", candidate_id: "reading-session-000001" }],
  books: [
    {
      candidate_id: "book-000001",
      file_hash: "sha256:one",
      title: "Matched Book",
      authors: ["Author One"],
      match: { status: "matched" as const, book_id: "local-book" },
      reading_sessions: [{
        candidate_id: "reading-session-000001",
        source_reading_session_id: "source-session-1",
        name: "  Imported session  ",
        notes: "  Notes stay put.  ",
        source_status: "active" as const,
        will_import_as_status: "closed" as const,
        started_at: "2026-01-01T00:00:00Z",
        closed_at: null,
        annotation_count: 3,
        will_import: true,
        possible_duplicate: true,
      }],
    },
    {
      candidate_id: "book-000002",
      file_hash: "sha256:two",
      title: "Missing Book",
      authors: [],
      match: { status: "unmatched" as const },
      reading_sessions: [{
        candidate_id: "reading-session-000002",
        source_reading_session_id: "source-session-2",
        name: "",
        notes: "",
        source_status: "closed" as const,
        will_import_as_status: "closed" as const,
        started_at: "2025-01-01T00:00:00Z",
        closed_at: "2025-01-02T00:00:00Z",
        annotation_count: 0,
        will_import: false,
        possible_duplicate: false,
      }],
    },
  ],
};

describe("Marginalia Import SDK", () => {
  it("sends the default empty-Session exclusion explicitly with Preview", async () => {
    const calls: RequestInit[] = [];
    const client: ApiClient = { request: async <T>(_path: string, init?: RequestInit) => {
      calls.push(init ?? {});
      return { ...previewResponse, include_empty_sessions: false } as T;
    } };

    await previewMarginaliaImport(new File(["{}"], "marginalia.json"), {}, client);

    expect(Array.from((calls[0]?.body as FormData).entries())).toEqual([
      ["file", expect.any(File)],
      ["include_empty_sessions", "false"],
    ]);
  });

  it("sends the canonical multipart preview and maps explicit candidates", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return previewResponse as T;
    } };
    const file = new File(["{}"], "marginalia.json", { type: "application/json" });

    const preview = await previewMarginaliaImport(file, { includeEmptySessions: true }, client);

    expect(calls[0]?.path).toBe("/api/v1/marginalia/import/preview/");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(Array.from((calls[0]?.init?.body as FormData).entries())).toEqual([
      ["file", file],
      ["include_empty_sessions", "true"],
    ]);
    expect(preview).toMatchObject({
      importToken: "opaque-preview-token",
      includeEmptySessions: true,
      canApply: true,
      summary: { bookCount: 2, readingSessionCount: 2, annotationCount: 3 },
      matchedBookCount: 1,
      unmatchedBookCount: 1,
      unmatchedReadingSessionCount: 1,
      unmatchedDownloadableReadingSessionCount: 1,
      books: [
        {
          candidateId: "book-000001",
          fileHash: "sha256:one",
          match: { status: "matched", bookId: "local-book" },
          readingSessions: [{
            candidateId: "reading-session-000001",
            sourceReadingSessionId: "source-session-1",
            name: "  Imported session  ",
            notes: "  Notes stay put.  ",
            sourceStatus: "active",
            willImportAsStatus: "closed",
            warnings: [{ code: "POSSIBLE_DUPLICATE_SESSION", candidateId: "reading-session-000001" }],
          }],
        },
        { candidateId: "book-000002", match: { status: "unmatched" } },
      ],
    });
  });

  it("maps the flat Apply request and authoritative candidate results", async () => {
    const calls: Array<{ path: string; init?: RequestInit }> = [];
    const client: ApiClient = { request: async <T>(path: string, init?: RequestInit) => {
      calls.push({ path, init });
      return {
        imported_reading_session_count: 1,
        imported_annotation_count: 3,
        reading_sessions: [{ candidate_id: "reading-session-000001", reading_session_id: "local-session", status: "closed", name: "Edited", annotation_count: 3 }],
        warnings: [{ code: "POSSIBLE_DUPLICATE_SESSION", message: "Possible duplicate.", candidate_id: "reading-session-000001" }],
      } as T;
    } };

    const result = await applyMarginaliaImport({
      importToken: "opaque-preview-token",
      readingSessions: [
        { candidateId: "reading-session-000001", name: "Edited", notes: "" },
        { candidateId: "reading-session-000002" },
      ],
    }, client);

    expect(calls[0]?.path).toBe("/api/v1/marginalia/import/apply/");
    expect(calls[0]?.init).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({
      import_token: "opaque-preview-token",
      reading_sessions: [
        { candidate_id: "reading-session-000001", name: "Edited", notes: "" },
        { candidate_id: "reading-session-000002" },
      ],
    });
    expect(result).toEqual({
      importedReadingSessionCount: 1,
      importedAnnotationCount: 3,
      readingSessions: [{ candidateId: "reading-session-000001", readingSessionId: "local-session", status: "closed", name: "Edited", annotationCount: 3 }],
      warnings: [{ code: "POSSIBLE_DUPLICATE_SESSION", message: "Possible duplicate.", candidateId: "reading-session-000001" }],
    });
  });

  it("downloads unmatched Sessions through attachment transport with the backend filename", async () => {
    const attachment: AttachmentDownload = {
      blob: new Blob(["zip"], { type: "application/zip" }),
      filename: "secondpass-marginalia-sessions.zip",
      contentType: "application/zip",
    };
    const requestAttachment = vi.fn(async () => attachment);
    const client: AttachmentApiClient = { requestAttachment };

    await expect(downloadUnmatchedMarginaliaImport("opaque token/+", client)).resolves.toBe(attachment);
    expect(requestAttachment).toHaveBeenCalledWith(
      "/api/v1/marginalia/import/unmatched/?import_token=opaque+token%2F%2B",
      undefined,
      "secondpass-marginalia-sessions.zip",
    );
  });

  it("preserves central bounded errors for preview, Apply, and unmatched download", async () => {
    const errors = [400, 404, 409].map((status) => new ApiError("Import failed.", status, { code: "INVALID_REQUEST" }));
    for (const error of errors) {
      const apiClient: ApiClient = { request: async () => Promise.reject(error) };
      const attachmentClient: AttachmentApiClient = { requestAttachment: async () => Promise.reject(error) };
      await expect(previewMarginaliaImport(new File(["{}"], "bad.json"), {}, apiClient)).rejects.toBe(error);
      await expect(applyMarginaliaImport({ importToken: "expired", readingSessions: [{ candidateId: "candidate" }] }, apiClient)).rejects.toBe(error);
      await expect(downloadUnmatchedMarginaliaImport("expired", attachmentClient)).rejects.toBe(error);
    }
  });
});
