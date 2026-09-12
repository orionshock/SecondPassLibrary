/** @vitest-environment happy-dom */

import type { MarginaliaImportPreview } from "@second-pass/spl-api";
import { act, useState } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarginaliaImportPageRegion } from "../../../../src/features/marginalia/import/MarginaliaImportPageRegion";
import { createMarginaliaImportDraft, type MarginaliaImportDraft } from "../../../../src/features/marginalia/import/marginaliaImportDraft";
import { buttonNamed } from "../../../support/domInteraction";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const preview: MarginaliaImportPreview = {
  importToken: "token", includeEmptySessions: false, canApply: true,
  summary: { bookCount: 3, readingSessionCount: 4, annotationCount: 4 },
  matchedBookCount: 2, unmatchedBookCount: 1, unmatchedReadingSessionCount: 1,
  unmatchedDownloadableReadingSessionCount: 1, warnings: [],
  books: [{
    candidateId: "book-1", fileHash: "sha256:one", title: "Covered Book", authors: ["Author"],
    match: { status: "matched", bookId: "local-book", coverUrl: "/media/covers/covered.jpg" },
    readingSessions: [session("session-1", "First Reading Session"), session("session-2", "Second Reading Session")],
  }, {
    candidateId: "book-2", fileHash: "sha256:coverless", title: "Coverless Book", authors: [],
    match: { status: "matched", bookId: "coverless-book", coverUrl: null },
    readingSessions: [session("session-4", "Coverless Reading Session")],
  }, {
    candidateId: "book-3", fileHash: "sha256:two", title: "Unmatched Book", authors: [],
    match: { status: "unmatched", reason: "not_found" },
    readingSessions: [{ ...session("session-3", "Unmatched Reading Session"), willImport: false }],
  }],
};

function session(candidateId: string, name: string) {
  return { candidateId, sourceReadingSessionId: `source-${candidateId}`, name, notes: "A note", sourceStatus: "closed" as const, willImportAsStatus: "closed" as const, startedAt: "2026-01-01T00:00:00Z", closedAt: "2026-01-02T00:00:00Z", annotationCount: 1, willImport: true, possibleDuplicate: false, warnings: [] };
}

let root: ReturnType<typeof createRoot> | undefined;
afterEach(async () => { if (root) await act(async () => root?.unmount()); root = undefined; document.body.replaceChildren(); });

async function mount() {
  const container = document.createElement("div"); document.body.append(container); root = createRoot(container);
  function Harness() {
    const [draft, setDraft] = useState<MarginaliaImportDraft>(() => createMarginaliaImportDraft(preview));
    const [editing, setEditing] = useState<ReadonlySet<string>>(new Set());
    return <MemoryRouter><MarginaliaImportPageRegion preview={preview} draft={draft} editingSessionKeys={editing} previewState={{ pending: false }} applyState={{ pending: false }} downloadState={{ pending: false }} inputRef={{ current: null }} includeEmptySessions={false} onIncludeEmptySessionsChange={vi.fn()} onFileChange={vi.fn()} onPreview={vi.fn()} onDraftChange={(key, value) => setDraft((current) => ({ ...current, [key]: value }))} onBookSelectionChange={(bookId, selected) => setDraft((current) => {
      const next = { ...current };
      preview.books.find((book) => book.candidateId === bookId)?.readingSessions.forEach((item) => { if (item.willImport) next[item.candidateId] = { ...next[item.candidateId]!, selected }; });
      return next;
    })} onEditingChange={(key, value) => setEditing(value ? new Set([key]) : new Set())} onDownloadUnmatched={vi.fn()} onApply={vi.fn()} /></MemoryRouter>;
  }
  await act(async () => root?.render(<Harness />)); return container;
}

describe("Marginalia import selection presentation", () => {
  it("uses the matched cover and keeps the generic unmatched fallback", async () => {
    const container = await mount();
    expect(container.querySelector('img[src="/media/covers/covered.jpg"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="No cover available for Coverless Book"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="No cover available for Unmatched Book"]')).not.toBeNull();
  });

  it("toggles a Reading Session card without double-toggling its checkbox or Edit action", async () => {
    const container = await mount();
    const checkbox = container.querySelector('[aria-label="Select First Reading Session for import"]') as HTMLInputElement;
    const card = checkbox.closest("article") as HTMLElement;
    await act(async () => card.click()); expect(checkbox.checked).toBe(false);
    await act(async () => checkbox.click()); expect(checkbox.checked).toBe(true);
    await act(async () => buttonNamed(card, "Edit First Reading Session").click()); expect(checkbox.checked).toBe(true);
  });

  it("selects a Book group and exposes mixed child selection as indeterminate", async () => {
    const container = await mount();
    const parent = container.querySelector('[aria-label="Select all importable Reading Sessions from Covered Book"]') as HTMLInputElement;
    const first = container.querySelector('[aria-label="Select First Reading Session for import"]') as HTMLInputElement;
    const second = container.querySelector('[aria-label="Select Second Reading Session for import"]') as HTMLInputElement;
    await act(async () => (parent.closest("section") as HTMLElement).click());
    expect(first.checked).toBe(false); expect(second.checked).toBe(false); expect(parent.checked).toBe(false);
    await act(async () => first.click());
    expect(first.checked).toBe(true); expect(second.checked).toBe(false); expect(parent.indeterminate).toBe(true); expect(parent.getAttribute("aria-checked")).toBe("mixed");
  });
});
