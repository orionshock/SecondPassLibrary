/** @vitest-environment happy-dom */

import type { MarginaliaExportCandidate, Page } from "@second-pass/spl-api";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarginaliaExportPageRegion } from "../../../../src/features/marginalia/export/MarginaliaExportPageRegion";
import { buttonNamed } from "../../../support/domInteraction";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const book = { id: "book-1", title: "A Book", coverUrl: "/media/covers/a.jpg", canOpen: true, authors: [{ id: "author-1", name: "An Author" }], series: { id: "series-1", name: "A Series", seriesIndex: "2.00" }, sessionCount: 2, activeSessionCount: 1, lastActivityAt: "2026-08-02T00:00:00Z" };
const sessions: MarginaliaExportCandidate[] = [candidate("session-1", "First Reading Session", "Keep this note."), candidate("session-2", "Second Reading Session", "")];
const page: Page<MarginaliaExportCandidate> = { items: sessions, count: 2, next: null, previous: null };

function candidate(id: string, name: string, notes: string): MarginaliaExportCandidate {
  return { id, name, notes, status: id === "session-1" ? "active" : "closed", startedAt: "2026-08-01T00:00:00Z", closedAt: id === "session-1" ? null : "2026-08-02T00:00:00Z", updatedAt: "2026-08-02T00:00:00Z", lastActivityAt: "2026-08-02T00:00:00Z", annotationCount: 2, book };
}

let root: ReturnType<typeof createRoot> | undefined;
afterEach(async () => { if (root) await act(async () => root?.unmount()); root = undefined; document.body.replaceChildren(); });

async function mount(initialView: "sessions" | "books" = "sessions") {
  const container = document.createElement("div"); document.body.append(container); root = createRoot(container);
  function Harness() {
    const [view, setView] = useState(initialView);
    const [selected, setSelected] = useState<ReadonlySet<string>>(new Set(["session-1"]));
    return <MemoryRouter><MarginaliaExportPageRegion page={page} pageNumber={1} pageSize={20} search="" status="all" view={view} loading={false} completeState={{ pending: false }} selectedState={{ pending: false }} selectedSessionIds={selected} selectedBookCount={selected.size ? 1 : 0} includeEmptySessions={false} onIncludeEmptySessionsChange={vi.fn()} onSearchChange={vi.fn()} onSearch={vi.fn()} onStatusChange={vi.fn()} onViewChange={setView} onPageChange={vi.fn()} onPageSizeChange={vi.fn()} onRetry={vi.fn()} onCompleteExport={vi.fn()} onSessionSelectionChange={(session, value) => setSelected((current) => {
      const next = new Set(current); if (value) next.add(session.id); else next.delete(session.id); return next;
    })} onSelectPage={vi.fn()} onClearSelection={() => setSelected(new Set())} onSelectedExport={vi.fn()} /></MemoryRouter>;
  }
  await act(async () => root?.render(<Harness />)); return container;
}

describe("Marginalia export selection views", () => {
  it("preserves selection across views and presents the normal Reading Session note", async () => {
    const container = await mount();
    const first = container.querySelector('[aria-label="Select First Reading Session for A Book"]') as HTMLInputElement;
    expect(first.checked).toBe(true); expect(container.textContent).toContain("Keep this note.");
    await act(async () => buttonNamed(container, "By Book").click());
    expect((container.querySelector('[aria-label="Select First Reading Session for A Book"]') as HTMLInputElement).checked).toBe(true);
    await act(async () => buttonNamed(container, "By Reading Session").click());
    expect((container.querySelector('[aria-label="Select First Reading Session for A Book"]') as HTMLInputElement).checked).toBe(true);
  });

  it("toggles a whole Reading Session card and does not double-toggle its checkbox", async () => {
    const container = await mount();
    const second = container.querySelector('[aria-label="Select Second Reading Session for A Book"]') as HTMLInputElement;
    await act(async () => (second.closest("article") as HTMLElement).click()); expect(second.checked).toBe(true);
    await act(async () => second.click()); expect(second.checked).toBe(false);
  });

  it("selects a Book group and exposes mixed child selection as indeterminate", async () => {
    const container = await mount("books");
    const parent = container.querySelector('[aria-label="Select Reading Sessions from A Book"]') as HTMLInputElement;
    expect(parent.indeterminate).toBe(true); expect(parent.getAttribute("aria-checked")).toBe("mixed");
    await act(async () => parent.click());
    expect(parent.checked).toBe(true);
    expect((container.querySelector('[aria-label="Select Second Reading Session for A Book"]') as HTMLInputElement).checked).toBe(true);
    await act(async () => (parent.closest("section") as HTMLElement).click());
    expect(parent.checked).toBe(false);
  });
});
