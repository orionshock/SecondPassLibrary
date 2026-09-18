/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryImportResult, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";
import { ImportsOrchestrator } from "../../../src/features/imports/ImportsOrchestrator";
import { buttonNamed, deferred, submit } from "../../support/domInteraction";

const sdk = vi.hoisted(() => ({ uploadLibraryImport: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  uploadLibraryImport: sdk.uploadLibraryImport,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const owner = {
  username: "owner", email: "", firstName: "", lastName: "", profileId: "owner", role: "manager",
  mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  installationId: "installation-id",
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: false,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev", releaseDate: "",
  publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;
const result: LibraryImportResult = {
  sourceType: "epub", sourceLabel: "book.epub",
  counts: { imported: 1, duplicate: 0, conflict: 0, failed: 0, skipped: 0 },
  items: [{
    status: "imported",
    sourceLabel: "book.epub",
    safeMessage: "",
    errorCategory: "",
    bookId: "book",
    title: "Imported Book",
  }],
};
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount(currentUser: CurrentUser = owner) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/imports", element: <ImportsOrchestrator /> }],
  }], { initialEntries: ["/imports"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return container;
}

function chooseFile(container: HTMLElement, file: File) {
  const input = container.querySelector<HTMLInputElement>("#library-import-file")!;
  Object.defineProperty(input, "files", { configurable: true, value: [file] });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

describe("ImportsOrchestrator", () => {
  it("uploads the selected archive and reconciles the authoritative result", async () => {
    sdk.uploadLibraryImport.mockResolvedValue(result);
    const container = await mount();
    const file = new File(["epub"], "book.epub", { type: "application/epub+zip" });

    await act(async () => chooseFile(container, file));
    await act(async () => submit(container.querySelector("form")!));

    expect(sdk.uploadLibraryImport).toHaveBeenCalledWith(file);
    expect(container.querySelector('a[href="/library/books/book"]')).not.toBeNull();
    expect(container.querySelector<HTMLInputElement>("#library-import-file")?.value).toBe("");
  });

  it("prevents a duplicate upload while the mutation is pending", async () => {
    const pending = deferred<LibraryImportResult>();
    sdk.uploadLibraryImport.mockReturnValue(pending.promise);
    const container = await mount();
    await act(async () => chooseFile(container, new File(["epub"], "book.epub")));

    await act(async () => submit(container.querySelector("form")!));
    const action = buttonNamed(container, "Importing...");
    expect(action.disabled).toBe(true);
    action.click();
    expect(sdk.uploadLibraryImport).toHaveBeenCalledOnce();
    await act(async () => pending.resolve(result));
  });

  it("keeps the selected file recoverable after an upload failure", async () => {
    sdk.uploadLibraryImport.mockRejectedValue(new Error("Import failed safely."));
    const container = await mount();
    const file = new File(["bad"], "broken.epub");
    await act(async () => chooseFile(container, file));

    await act(async () => submit(container.querySelector("form")!));

    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Import failed safely.");
    expect(container.querySelector<HTMLInputElement>("#library-import-file")?.files?.[0]).toBe(file);
    expect(buttonNamed(container, "Import").disabled).toBe(false);
  });

  it("does not expose or call the upload operation for a Reader", async () => {
    const container = await mount({ ...owner, isOwner: false, isReader: true, role: "reader" });

    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(sdk.uploadLibraryImport).not.toHaveBeenCalled();
  });
});
