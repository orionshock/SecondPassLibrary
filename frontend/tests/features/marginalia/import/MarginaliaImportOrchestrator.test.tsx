/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, MarginaliaImportApplyResult, MarginaliaImportPreview, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { MarginaliaImportOrchestrator } from "../../../../src/features/marginalia/import/MarginaliaImportOrchestrator";
import { buttonNamed, deferred, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ preview: vi.fn(), apply: vi.fn(), download: vi.fn() }));
const browser = vi.hoisted(() => ({ save: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  previewMarginaliaImport: sdk.preview,
  applyMarginaliaImport: sdk.apply,
  downloadUnmatchedMarginaliaImport: sdk.download,
}));
vi.mock("../../../../src/shared/browser/saveDownloadedFile", () => ({ saveDownloadedFile: browser.save }));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const preview: MarginaliaImportPreview = {
  importToken: "import-token", includeEmptySessions: true, canApply: true,
  summary: { bookCount: 1, readingSessionCount: 1, annotationCount: 2 }, matchedBookCount: 1,
  unmatchedBookCount: 0, unmatchedReadingSessionCount: 0, unmatchedDownloadableReadingSessionCount: 1,
  warnings: [],
  books: [{
    candidateId: "book-candidate", fileHash: "hidden", title: "Imported Book", authors: ["Author"],
    match: { status: "matched", bookId: "book-id", coverUrl: null },
    readingSessions: [{
      candidateId: "session-candidate", sourceReadingSessionId: "source-session", name: "Imported Session",
      notes: "Notes", sourceStatus: "active", willImportAsStatus: "closed", startedAt: "2026-01-01T00:00:00Z",
      closedAt: null, annotationCount: 2, willImport: true, possibleDuplicate: false, warnings: [],
    }],
  }],
};
const result: MarginaliaImportApplyResult = {
  importedReadingSessionCount: 1, importedAnnotationCount: 2, unmatchedReadingSessionCount: 0,
  unmatchedDownloadableReadingSessionCount: 1, unmatchedDownloadAvailable: true, unmatchedBooks: [],
  readingSessions: [{ candidateId: "session-candidate", readingSessionId: "created-session", status: "closed", name: "Imported Session", annotationCount: 2 }],
  warnings: [],
};
const currentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader",
  mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true,
  canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  installationId: "installation-id",
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: false,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev", releaseDate: "",
  publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount() {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/marginalia/import", element: <MarginaliaImportOrchestrator /> }],
  }], { initialEntries: ["/marginalia/import"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return container;
}

function chooseFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

async function loadPreview(container: HTMLElement) {
  const file = new File(["{}"], "marginalia.json", { type: "application/json" });
  act(() => chooseFile(container.querySelector("#marginalia-import-file")!, file));
  await act(async () => submit(container.querySelector("form")!));
  return file;
}

describe("MarginaliaImportOrchestrator", () => {
  it("previews the selected archive with the staged empty-Session policy", async () => {
    sdk.preview.mockResolvedValue(preview);
    const container = await mount();
    act(() => Array.from(container.querySelectorAll<HTMLInputElement>('input[type="checkbox"]'))[0]?.click());
    const file = await loadPreview(container);

    expect(sdk.preview).toHaveBeenCalledWith(file, { includeEmptySessions: true });
    expect(container.querySelector('[aria-label="Import preview summary"]')).not.toBeNull();
  });

  it("rejects a stale preview after the selected archive changes", async () => {
    const request = deferred<MarginaliaImportPreview>();
    sdk.preview.mockReturnValue(request.promise);
    const container = await mount();
    const first = new File(["one"], "one.json", { type: "application/json" });
    const second = new File(["two"], "two.json", { type: "application/json" });
    const input = container.querySelector("#marginalia-import-file") as HTMLInputElement;
    act(() => {
      chooseFile(input, first);
      submit(container.querySelector("form")!);
      chooseFile(input, second);
    });
    await act(async () => request.resolve(preview));

    expect(container.querySelector('[aria-label="Import preview summary"]')).toBeNull();
  });

  it("applies the selected staged Sessions once and renders authoritative results", async () => {
    sdk.preview.mockResolvedValue(preview);
    const pending = deferred<MarginaliaImportApplyResult>();
    sdk.apply.mockReturnValue(pending.promise);
    const container = await mount();
    await loadPreview(container);

    act(() => buttonNamed(container, "Import selected").click());
    expect(sdk.apply).toHaveBeenCalledWith({ importToken: "import-token", readingSessions: [{ candidateId: "session-candidate" }] });
    expect(buttonNamed(container, "Importing…").disabled).toBe(true);
    act(() => buttonNamed(container, "Importing…").click());
    expect(sdk.apply).toHaveBeenCalledOnce();

    await act(async () => pending.resolve(result));
    expect(container.querySelector('a[href="/marginalia/sessions/created-session"]')).not.toBeNull();
  });

  it("keeps the staged review recoverable after apply failure", async () => {
    sdk.preview.mockResolvedValue(preview);
    sdk.apply.mockRejectedValue(new Error("Apply failed."));
    const container = await mount();
    await loadPreview(container);

    await act(async () => buttonNamed(container, "Import selected").click());

    expect(container.querySelector('[aria-label="Import preview summary"]')).not.toBeNull();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
  });

  it("downloads unmatched staged data through the browser save boundary", async () => {
    sdk.preview.mockResolvedValue(preview);
    const download = { blob: new Blob(["archive"]), filename: "unmatched.json" };
    sdk.download.mockResolvedValue(download);
    const container = await mount();
    await loadPreview(container);

    await act(async () => buttonNamed(container, "Download unmatched (1)").click());

    expect(sdk.download).toHaveBeenCalledWith("import-token");
    expect(browser.save).toHaveBeenCalledWith(download);
  });
});
