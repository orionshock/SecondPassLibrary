import { afterEach, describe, expect, it, vi } from "vitest";

import { saveDownloadedFile } from "../../../src/shared/browser/saveDownloadedFile";

describe("saveDownloadedFile", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("creates, clicks, removes, and revokes a temporary download link", () => {
    const anchor = { href: "", download: "", hidden: false, click: vi.fn(), remove: vi.fn() };
    const append = vi.fn();
    const createObjectURL = vi.fn(() => "blob:download");
    const revokeObjectURL = vi.fn();
    vi.stubGlobal("document", { createElement: vi.fn(() => anchor), body: { append } });
    vi.stubGlobal("URL", { createObjectURL, revokeObjectURL });

    const blob = new Blob(["archive"]);
    saveDownloadedFile({ blob, filename: "marginalia.json" });

    expect(createObjectURL).toHaveBeenCalledWith(blob);
    expect(anchor).toMatchObject({ href: "blob:download", download: "marginalia.json", hidden: true });
    expect(append).toHaveBeenCalledWith(anchor);
    expect(anchor.click).toHaveBeenCalledOnce();
    expect(anchor.remove).toHaveBeenCalledOnce();
    expect(revokeObjectURL).toHaveBeenCalledWith("blob:download");
  });
});

