/** @vitest-environment happy-dom */

import type { MarginaliaBookSummary, MarginaliaSessionSummary, Page } from "@second-pass/spl-api";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { MarginaliaViewSelector } from "../../../../src/features/marginalia/browse/MarginaliaViewSelector";
import { MarginaliaBooksPageRegion } from "../../../../src/features/marginalia/browse/MarginaliaBooksPageRegion";
import { MarginaliaSessionsPageRegion } from "../../../../src/features/marginalia/browse/MarginaliaSessionsPageRegion";

const book: MarginaliaBookSummary = {
  id: "11111111-1111-4111-8111-111111111111",
  title: "Battle Ground",
  authors: [{ id: "author-1", name: "Jim Butcher" }],
  series: { id: "series-1", name: "Dresden Files", seriesIndex: "18.00" },
  coverUrl: "/media/battle-ground.jpg",
  canOpen: true,
  sessionCount: 3,
  activeSessionCount: 1,
  lastActivityAt: "2026-07-30T12:00:00Z",
};

const session: MarginaliaSessionSummary = {
  id: "22222222-2222-4222-8222-222222222222",
  name: "Second pass",
  notes: "A Session note",
  status: "closed",
  startedAt: "2026-07-01T12:00:00Z",
  closedAt: "2026-07-20T12:00:00Z",
  updatedAt: "2026-07-20T12:00:00Z",
  lastActivityAt: "2026-07-21T12:00:00Z",
  annotationCount: 12,
};

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

describe("Marginalia view selector", () => {
  it("marks the current view and changes modes without tab semantics", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onViewChange = vi.fn();
    await act(async () => root?.render(<MarginaliaViewSelector activeView="sessions" onViewChange={onViewChange} />));
    const group = container.querySelector<HTMLElement>('[role="group"][aria-label="Marginalia views"]')!;
    const buttons = group.querySelectorAll<HTMLButtonElement>("button");
    expect(buttons[0]!.getAttribute("aria-pressed")).toBe("true");
    expect(buttons[0]!.textContent).toContain("Reading Sessions");
    expect(buttons[1]!.textContent).toContain("Books");
    expect(container.querySelector('[role="tablist"]')).toBeNull();

    await act(async () => buttons[1]!.click());
    expect(onViewChange).toHaveBeenCalledWith("books");
  });
});

describe("Marginalia Books view", () => {
  it("renders the bounded canonical Book projection through the compact Book row", () => {
    const page: Page<MarginaliaBookSummary> = { items: [book], count: 21, next: "/next", previous: null };
    const markup = renderToStaticMarkup(<MemoryRouter><MarginaliaBooksPageRegion
      page={page}
      pageNumber={1}
      pageSize={20}
      search="battle"
      loading={false}
      bookPath={(bookId) => `/marginalia?view=books&book=${bookId}&q=battle`}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(markup).toContain("Battle Ground");
    expect(markup).toContain("Jim Butcher");
    expect(markup).toContain("Dresden Files 18.0");
    expect(markup).toContain("3 Reading Sessions");
    expect(markup).toContain("1 active");
    expect(markup).toContain(`href="/marginalia?view=books&amp;book=${book.id}&amp;q=battle"`);
    expect(markup).toContain(`href="/library/books/${book.id}"`);
    expect(markup).toContain("Showing 1-20 of 21");
    expect(markup).not.toContain("Catalog Tags");
    expect(markup).not.toContain("Publisher");
  });

  it("keeps inaccessible owned Book identity selectable without a Library action", () => {
    const hidden = { ...book, title: "Remembered Book", canOpen: false };
    const markup = renderToStaticMarkup(<MemoryRouter><MarginaliaBooksPageRegion
      page={{ items: [hidden], count: 1, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      search=""
      loading={false}
      bookPath={(bookId) => `/marginalia?view=books&book=${bookId}`}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(markup).toContain("Remembered Book");
    expect(markup).toContain(`/marginalia?view=books&amp;book=${book.id}`);
    expect(markup).not.toContain(`/library/books/${book.id}`);
  });
});

describe("Marginalia selected Book Session stage", () => {
  it("reuses canonical Book context and Session cards inside the browse surface", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><MarginaliaSessionsPageRegion
      page={{ items: [session], count: 1, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      search="note"
      status="closed"
      loading={false}
      bookContext={{ ...book, canOpen: false }}
      onBackToBooks={vi.fn()}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onStatusChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(markup).toContain("Battle Ground");
    expect(markup).toContain("Back to Books");
    expect(markup).toContain('<option value="closed" selected="">Closed</option>');
    expect(markup).toContain("Second pass");
    expect(markup).toContain(`/marginalia/sessions/${session.id}`);
    expect(markup).not.toContain(`/library/books/${book.id}`);
  });

  it("keeps a bounded error and return action when selected Book access disappears", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><MarginaliaSessionsPageRegion
      page={undefined}
      pageNumber={1}
      pageSize={20}
      search=""
      status="all"
      loading={false}
      error={new Error("Marginalia Book unavailable.")}
      onBackToBooks={vi.fn()}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onStatusChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(markup).toContain("Marginalia Book unavailable.");
    expect(markup).toContain("Back to Books");
    expect(markup).toContain("Retry");
  });
});
