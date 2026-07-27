import { describe, expect, it, vi } from "vitest";

import type { AttachmentApiClient, AttachmentDownload } from "../client";
import { downloadCompleteReadingExport, downloadSelectedReadingExport } from "../reading";

const attachment: AttachmentDownload = {
  blob: new Blob(["archive"], { type: "application/json" }),
  filename: "second-pass-marginalia.json",
  contentType: "application/json",
};

describe("reading export SDK", () => {
  it("downloads the complete owned archive", async () => {
    const requestAttachment = vi.fn(async (_path: string, _init?: RequestInit, _fallbackFilename?: string) => attachment);
    const client: AttachmentApiClient = { requestAttachment };

    await expect(downloadCompleteReadingExport(client)).resolves.toBe(attachment);
    expect(requestAttachment).toHaveBeenCalledWith("/api/v1/reading/export/", undefined, "second-pass-marginalia.json");
  });

  it("groups selected Sessions by Book and removes duplicate Sessions", async () => {
    const requestAttachment = vi.fn(async (_path: string, _init?: RequestInit, _fallbackFilename?: string) => attachment);
    const client: AttachmentApiClient = { requestAttachment };

    await expect(downloadSelectedReadingExport({ sessions: [
      { sessionId: "session-1", bookId: "book-1" },
      { sessionId: "session-2", bookId: "book-1" },
      { sessionId: "session-1", bookId: "book-1" },
      { sessionId: "session-3", bookId: "book-2" },
    ] }, client)).resolves.toBe(attachment);

    const [, init, fallback] = requestAttachment.mock.calls[0]!;
    expect(init).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(String(init?.body))).toEqual({ books: [
      { book_id: "book-1", sessions: ["session-1", "session-2"] },
      { book_id: "book-2", sessions: ["session-3"] },
    ] });
    expect(fallback).toBe("second-pass-marginalia.json");
  });

  it("preserves structured attachment errors", async () => {
    const error = new Error("structured");
    const client: AttachmentApiClient = { requestAttachment: async () => Promise.reject(error) };
    await expect(downloadCompleteReadingExport(client)).rejects.toBe(error);
    await expect(downloadSelectedReadingExport({ sessions: [] }, client)).rejects.toBe(error);
  });
});
