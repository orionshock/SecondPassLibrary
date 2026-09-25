/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, MemoryRouter, Route, RouterProvider, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MarginaliaSessionEnvelope } from "@second-pass/spl-api";
import { buttonNamed, deferred, setControlValue } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  getSession: vi.fn(),
  listAnnotations: vi.fn(),
  updateSession: vi.fn(),
  closeSession: vi.fn(),
  deleteSession: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getMarginaliaSession: sdk.getSession,
  listMarginaliaSessionAnnotations: sdk.listAnnotations,
  updateMarginaliaSession: sdk.updateSession,
  closeMarginaliaSession: sdk.closeSession,
  deleteMarginaliaSession: sdk.deleteSession,
}));
vi.mock("../../../../src/app/navigation/usePageBreadcrumbs", () => ({ usePageBreadcrumbs: vi.fn() }));

import { MarginaliaSessionDetailOrchestrator } from "../../../../src/features/marginalia/sessionDetail/MarginaliaSessionDetailOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

const detail = {
  book: { id: "book/id", title: "Visible Book", authors: [], series: null, coverUrl: null, canOpen: true, sessionCount: 2, activeSessionCount: 1, lastActivityAt: "2026-01-03T00:00:00Z" },
  session: { id: "session-id", name: "Evening read", notes: "Session note", status: "active", startedAt: "2026-01-01T00:00:00Z", closedAt: null, updatedAt: "2026-01-03T00:00:00Z", lastActivityAt: "2026-01-03T00:00:00Z", annotationCount: 1, progress: null },
} satisfies MarginaliaSessionEnvelope;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

function detailWith(
  session: Partial<MarginaliaSessionEnvelope["session"]>,
): MarginaliaSessionEnvelope {
  return { ...detail, session: { ...detail.session, ...session } };
}

async function mountDetail(path = "/marginalia/sessions/session-id") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const router = createMemoryRouter([
    { path: "/marginalia/sessions/:sessionId", element: <MarginaliaSessionDetailOrchestrator /> },
    { path: "/marginalia", element: <p>Marginalia home</p> },
  ], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

async function beginNameSave(container: HTMLElement, name: string) {
  await act(async () => buttonNamed(container, "Edit Reading Session name").click());
  await act(async () => setControlValue(
    container.querySelector<HTMLInputElement>('[aria-label="Reading Session name"]')!,
    name,
  ));
  act(() => buttonNamed(container, "Save Reading Session name").click());
}

async function beginNoteSave(container: HTMLElement, note: string) {
  await act(async () => buttonNamed(container, "Edit Reading Session note").click());
  await act(async () => setControlValue(
    container.querySelector<HTMLTextAreaElement>('[aria-label="Reading Session note"]')!,
    note,
  ));
  act(() => buttonNamed(container, "Save Reading Session note").click());
}

function actionButtonContaining(container: HTMLElement, label: string): HTMLButtonElement {
  const button = Array.from(container.querySelectorAll<HTMLButtonElement>("button"))
    .find((candidate) => candidate.textContent?.includes(label));
  if (!button) throw new Error(`Button not found containing: ${label}`);
  return button;
}

describe("MarginaliaSessionDetailOrchestrator", () => {
  it("loads the Session and its annotations without displaying selector context", async () => {
    sdk.getSession.mockResolvedValue(detail);
    sdk.listAnnotations.mockResolvedValue([{
      id: "annotation-id", clientId: "client-id", kind: "highlight",
      location: { location: "epubcfi(/6/4)", locationLabel: "Chapter 2" },
      body: { text: "Selected quote", prefix: "hidden prefix", suffix: "hidden suffix", note: "Reader note" },
      createdAt: "2026-01-02T00:00:00Z", updatedAt: "2026-01-02T00:00:00Z",
    }]);
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => root?.render(
      <MemoryRouter initialEntries={["/marginalia/sessions/session-id"]}>
        <Routes><Route path="/marginalia/sessions/:sessionId" element={<MarginaliaSessionDetailOrchestrator />} /></Routes>
      </MemoryRouter>,
    ));

    expect(sdk.getSession).toHaveBeenCalledWith("session-id");
    expect(sdk.listAnnotations).toHaveBeenCalledWith("session-id");
    expect(container.textContent).toContain("Selected quote");
    expect(container.textContent).toContain("Reader note");
    expect(container.textContent).not.toContain("hidden prefix");
    expect(container.textContent).not.toContain("hidden suffix");
    expect(container.querySelector('a[href="/library/books/book%2Fid"]')).not.toBeNull();
    expect(container.querySelector('a[href="/marginalia?view=books&book=book%2Fid"]')).not.toBeNull();
  });

  it("offers a retry after the Session load fails", async () => {
    sdk.getSession.mockRejectedValueOnce(new Error("Session unavailable.")).mockResolvedValueOnce(detail);
    sdk.listAnnotations.mockResolvedValue([]);
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root?.render(<MemoryRouter initialEntries={["/marginalia/sessions/session-id"]}><Routes><Route path="/marginalia/sessions/:sessionId" element={<MarginaliaSessionDetailOrchestrator />} /></Routes></MemoryRouter>));

    expect(container.textContent).toContain("Session unavailable.");
    const retry = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Retry")!;
    await act(async () => retry.click());
    expect(sdk.getSession).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain("Evening read");
  });

  it("keeps close authoritative when an earlier rename resolves afterward", async () => {
    const rename = deferred<MarginaliaSessionEnvelope>();
    const close = deferred<MarginaliaSessionEnvelope>();
    sdk.getSession.mockResolvedValue(detail);
    sdk.listAnnotations.mockResolvedValue([]);
    sdk.updateSession.mockReturnValue(rename.promise);
    sdk.closeSession.mockReturnValue(close.promise);
    const { container } = await mountDetail();

    await beginNameSave(container, "Renamed Session");
    act(() => actionButtonContaining(container, "Close Reading Session").click());
    await act(async () => close.resolve(detailWith({
      status: "closed",
      closedAt: "2026-01-04T00:00:00Z",
    })));

    expect(container.textContent).toContain("Closed");
    expect(container.querySelector('[aria-label="Edit Reading Session name"]')).toBeNull();
    expect(container.querySelector('[aria-label="Edit Reading Session note"]')).toBeNull();

    await act(async () => rename.resolve(detailWith({ name: "Renamed Session" })));

    expect(container.textContent).toContain("Closed");
    expect(container.querySelector('[aria-label="Edit Reading Session name"]')).toBeNull();
    expect(container.querySelector('[aria-label="Edit Reading Session note"]')).toBeNull();
  });

  it("merges overlapping name and note results without erasing either field", async () => {
    const rename = deferred<MarginaliaSessionEnvelope>();
    const note = deferred<MarginaliaSessionEnvelope>();
    sdk.getSession.mockResolvedValue(detail);
    sdk.listAnnotations.mockResolvedValue([]);
    sdk.updateSession
      .mockReturnValueOnce(rename.promise)
      .mockReturnValueOnce(note.promise);
    const { container } = await mountDetail();

    await beginNameSave(container, "Renamed Session");
    await beginNoteSave(container, "Updated note");
    await act(async () => note.resolve(detailWith({ notes: "Updated note" })));
    await act(async () => rename.resolve(detailWith({ name: "Renamed Session" })));

    expect(container.querySelector("h1")?.textContent).toContain("Renamed Session");
    expect(container.textContent).toContain("Updated note");
  });

  it("invalidates mutation publication when the route selects another Session", async () => {
    const oldRename = deferred<MarginaliaSessionEnvelope>();
    const nextDetail = {
      ...detailWith({ id: "session-b", name: "Session B" }),
      book: { ...detail.book, id: "book-b", title: "Book B" },
    };
    sdk.getSession.mockImplementation((sessionId: string) => (
      sessionId === "session-b" ? Promise.resolve(nextDetail) : Promise.resolve(detail)
    ));
    sdk.listAnnotations.mockResolvedValue([]);
    sdk.updateSession.mockReturnValue(oldRename.promise);
    const { container, router } = await mountDetail();

    await beginNameSave(container, "Stale Session A");
    await act(async () => router.navigate("/marginalia/sessions/session-b"));
    expect(container.querySelector("h1")?.textContent).toContain("Session B");

    await act(async () => oldRename.resolve(detailWith({ name: "Stale Session A" })));

    expect(container.querySelector("h1")?.textContent).toContain("Session B");
    expect(container.textContent).not.toContain("Stale Session A");
    expect(container.textContent).not.toContain("Reading Session name saved.");
  });

  it("keeps successful deletion navigation authoritative over an older mutation", async () => {
    const rename = deferred<MarginaliaSessionEnvelope>();
    const deletion = deferred<void>();
    sdk.getSession.mockResolvedValue(detail);
    sdk.listAnnotations.mockResolvedValue([]);
    sdk.updateSession.mockReturnValue(rename.promise);
    sdk.deleteSession.mockReturnValue(deletion.promise);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mountDetail();

    await beginNameSave(container, "Stale after delete");
    act(() => actionButtonContaining(container, "Delete").click());
    act(() => buttonNamed(container, "Continue").click());
    await act(async () => deletion.resolve(undefined));
    expect(router.state.location.pathname).toBe("/marginalia");

    await act(async () => rename.resolve(detailWith({ name: "Stale after delete" })));

    expect(router.state.location.pathname).toBe("/marginalia");
    expect(container.textContent).toContain("Marginalia home");
    expect(container.textContent).not.toContain("Stale after delete");
  });

  it("keeps the current envelope and permits retry after a mutation fails", async () => {
    const failedRename = deferred<MarginaliaSessionEnvelope>();
    sdk.getSession.mockResolvedValue(detail);
    sdk.listAnnotations.mockResolvedValue([]);
    sdk.updateSession
      .mockReturnValueOnce(failedRename.promise)
      .mockResolvedValueOnce(detailWith({ name: "Retried Session" }));
    const { container } = await mountDetail();

    await beginNameSave(container, "Failed Session");
    await act(async () => failedRename.reject(new Error("Rename failed.")));

    expect(container.textContent).toContain("Rename failed.");
    expect(container.querySelector<HTMLInputElement>('[aria-label="Reading Session name"]')?.disabled).toBe(false);
    act(() => buttonNamed(container, "Cancel editing Reading Session name").click());
    expect(container.querySelector("h1")?.textContent).toContain("Evening read");

    await beginNameSave(container, "Retried Session");
    await act(async () => undefined);

    expect(sdk.updateSession).toHaveBeenCalledTimes(2);
    expect(container.querySelector("h1")?.textContent).toContain("Retried Session");
  });
});
