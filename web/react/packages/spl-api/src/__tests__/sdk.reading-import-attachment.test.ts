import { describe, expect, it, vi } from "vitest";

import type { AttachmentApiClient, AttachmentDownload } from "../client";
import { downloadUnmatchedReadingImport } from "../reading";

const attachment: AttachmentDownload = {
  blob: new Blob(["archive"], { type: "application/json" }),
  filename: "second-pass-marginalia.json",
  contentType: "application/json",
};

describe("reading import attachment SDK", () => {
  it("downloads unmatched import Sessions with the opaque token", async () => {
    const archive = { ...attachment, filename: "secondpass-marginalia-sessions.zip", contentType: "application/zip" };
    const requestAttachment = vi.fn(async () => archive);
    const client: AttachmentApiClient = { requestAttachment };

    await expect(downloadUnmatchedReadingImport("opaque token/+", client)).resolves.toBe(archive);
    expect(requestAttachment).toHaveBeenCalledWith(
      "/api/v1/reading/import/unmatched/?import_token=opaque+token%2F%2B",
      undefined,
      "secondpass-marginalia-sessions.zip",
    );
  });

  it("preserves unmatched import attachment errors", async () => {
    const error = new Error("structured");
    const client: AttachmentApiClient = { requestAttachment: async () => Promise.reject(error) };
    await expect(downloadUnmatchedReadingImport("expired", client)).rejects.toBe(error);
  });
});
