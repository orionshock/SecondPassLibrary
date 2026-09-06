/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, MarginaliaSessionListItem, Page, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { MarginaliaExportOrchestrator } from "../../../../src/features/marginalia/export/MarginaliaExportOrchestrator";
import { buttonNamed, deferred } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ listSessions: vi.fn(), downloadComplete: vi.fn(), downloadSelected: vi.fn() }));
const browser = vi.hoisted(() => ({ save: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listMarginaliaSessions: sdk.listSessions,
  downloadCompleteMarginaliaExport: sdk.downloadComplete,
  downloadSelectedMarginaliaExport: sdk.downloadSelected,
}));
vi.mock("../../../../src/shared/browser/saveDownloadedFile", () => ({ saveDownloadedFile: browser.save }));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const session = (id: string, name: string): MarginaliaSessionListItem => ({
  id, name, notes: "", status: "active", startedAt: "2026-01-01T00:00:00Z", closedAt: null,
  updatedAt: "2026-01-01T00:00:00Z", lastActivityAt: "2026-01-01T00:00:00Z", annotationCount: 1,
  book: { id: `book-${id}`, title: `Book ${name}`, coverUrl: null, canOpen: true },
});
const page = (items: MarginaliaSessionListItem[]): Page<MarginaliaSessionListItem> => ({ items, count: items.length, next: null, previous: null });
const currentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader",
  mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true,
  canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
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

async function mount(path = "/marginalia/export") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/marginalia/export", element: <MarginaliaExportOrchestrator /> }],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("MarginaliaExportOrchestrator", () => {
  it("loads URL-backed export candidates and retries a recoverable failure", async () => {
    sdk.listSessions.mockRejectedValueOnce(new Error("Candidates unavailable.")).mockResolvedValueOnce(page([session("recovered", "Recovered")]));
    const { container } = await mount("/marginalia/export?q=notes&status=closed&page=2&page_size=50");
    expect(sdk.listSessions).toHaveBeenCalledWith({ q: "notes", status: "closed", hasAnnotations: true, page: 2, pageSize: 50 });
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listSessions).toHaveBeenCalledTimes(2);
    expect(container.querySelector('[aria-label="Select Recovered"]')).not.toBeNull();
  });

  it("downloads a complete archive once and sends it through the browser save boundary", async () => {
    sdk.listSessions.mockResolvedValue(page([]));
    const pending = deferred<{ blob: Blob; filename: string }>();
    sdk.downloadComplete.mockReturnValue(pending.promise);
    const download = { blob: new Blob(["archive"]), filename: "complete.json" };
    const { container } = await mount();

    act(() => buttonNamed(container, "Download complete archive").click());
    expect(sdk.downloadComplete).toHaveBeenCalledWith({ includeEmptySessions: false });
    expect(buttonNamed(container, "Preparing...").disabled).toBe(true);
    act(() => buttonNamed(container, "Preparing...").click());
    expect(sdk.downloadComplete).toHaveBeenCalledOnce();
    await act(async () => pending.resolve(download));

    expect(browser.save).toHaveBeenCalledWith(download);
  });

  it("exports only selected Sessions and preserves selection after download failure", async () => {
    sdk.listSessions.mockResolvedValue(page([session("one", "Selected Session")]));
    sdk.downloadSelected.mockRejectedValue(new Error("Selected export failed."));
    const { container } = await mount();
    act(() => (container.querySelector('[aria-label="Select Selected Session"]') as HTMLInputElement).click());

    await act(async () => buttonNamed(container, "Export selected Sessions").click());

    expect(sdk.downloadSelected).toHaveBeenCalledWith({ readingSessionIds: ["one"], includeEmptySessions: false });
    expect((container.querySelector('[aria-label="Select Selected Session"]') as HTMLInputElement).checked).toBe(true);
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
  });

  it("does not allow an older candidate request to replace a newer filter result", async () => {
    const oldRequest = deferred<Page<MarginaliaSessionListItem>>();
    const newRequest = deferred<Page<MarginaliaSessionListItem>>();
    sdk.listSessions.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    const { container, router } = await mount("/marginalia/export?q=old");

    await act(async () => router.navigate("/marginalia/export?q=new"));
    await act(async () => newRequest.resolve(page([session("new", "New Candidate")])));
    await act(async () => oldRequest.resolve(page([session("old", "Old Candidate")])));

    expect(container.querySelector('[aria-label="Select New Candidate"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Select Old Candidate"]')).toBeNull();
  });
});
