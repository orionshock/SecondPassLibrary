/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { MarginaliaSessionEnvelope } from "@second-pass/spl-api";

const sdk = vi.hoisted(() => ({ getSession: vi.fn(), listAnnotations: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getMarginaliaSession: sdk.getSession,
  listMarginaliaSessionAnnotations: sdk.listAnnotations,
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
  vi.clearAllMocks();
});

describe("MarginaliaSessionDetailOrchestrator", () => {
  it("loads the Session and its annotations without displaying selector context", async () => {
    sdk.getSession.mockResolvedValue(detail);
    sdk.listAnnotations.mockResolvedValue([{
      id: "annotation-id", clientId: "client-id", kind: "highlight",
      location: { cfi: "epubcfi(/6/4)", locationLabel: "Chapter 2" },
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
});
