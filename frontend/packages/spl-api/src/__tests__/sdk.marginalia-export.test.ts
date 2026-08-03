import { describe, expect, it, vi } from "vitest";

import type { AttachmentApiClient, AttachmentDownload } from "../client";
import { ApiError } from "../errors";
import { downloadCompleteMarginaliaExport, downloadSelectedMarginaliaExport } from "../marginalia";

const attachment: AttachmentDownload = {
  blob: new Blob(["archive"], { type: "application/json" }),
  filename: "20260730-second-pass-marginalia.json",
  contentType: "application/json; charset=utf-8",
};

describe("Marginalia Export SDK", () => {
  it("downloads the complete archive and omits the default empty-Session policy", async () => {
    const requestAttachment = vi.fn(async (_path: string, _init?: RequestInit, _fallbackFilename?: string) => attachment);
    const client: AttachmentApiClient = { requestAttachment };

    await expect(downloadCompleteMarginaliaExport({}, client)).resolves.toBe(attachment);
    expect(requestAttachment).toHaveBeenCalledWith(
      "/api/v1/marginalia/export/",
      undefined,
      "second-pass-marginalia.json",
    );
  });

  it("maps complete export empty-Session opt-in", async () => {
    const requestAttachment = vi.fn(async (_path: string, _init?: RequestInit, _fallbackFilename?: string) => attachment);
    const client: AttachmentApiClient = { requestAttachment };

    await downloadCompleteMarginaliaExport({ includeEmptySessions: true }, client);
    expect(requestAttachment).toHaveBeenCalledWith(
      "/api/v1/marginalia/export/?include_empty_sessions=true",
      undefined,
      "second-pass-marginalia.json",
    );
  });

  it("maps selected Reading Session identities and the empty-Session policy", async () => {
    const requestAttachment = vi.fn(async (_path: string, _init?: RequestInit, _fallbackFilename?: string) => attachment);
    const client: AttachmentApiClient = { requestAttachment };

    await downloadSelectedMarginaliaExport({
      readingSessionIds: ["session-2", "session-1"],
      includeEmptySessions: true,
    }, client);

    const [path, init, fallback] = requestAttachment.mock.calls[0]!;
    expect(path).toBe("/api/v1/marginalia/export/");
    expect(init).toMatchObject({ method: "POST", headers: { "Content-Type": "application/json" } });
    expect(JSON.parse(String(init?.body))).toEqual({
      reading_session_ids: ["session-2", "session-1"],
      include_empty_sessions: true,
    });
    expect(fallback).toBe("second-pass-marginalia.json");
  });

  it("preserves the attachment result and bounded SDK errors", async () => {
    const error = new ApiError("Nothing to export.", 409, { code: "INVALID_REQUEST" });
    const successClient: AttachmentApiClient = { requestAttachment: async () => attachment };
    const errorClient: AttachmentApiClient = { requestAttachment: async () => Promise.reject(error) };

    await expect(downloadSelectedMarginaliaExport({ readingSessionIds: ["session-1"] }, successClient))
      .resolves.toBe(attachment);
    await expect(downloadCompleteMarginaliaExport({}, errorClient)).rejects.toBe(error);
  });
});
