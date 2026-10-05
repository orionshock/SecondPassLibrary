/** @vitest-environment happy-dom */

import type { MarginaliaAnnotation, MarginaliaSessionEnvelope } from "@second-pass/spl-api";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { appRoutes } from "../../../../src/app/router";
import { marginaliaSessionBreadcrumbFallback } from "../../../../src/features/marginalia/marginaliaBreadcrumbs";
import { MarginaliaSessionNoteEditor } from "../../../../src/features/marginalia/sessionDetail/MarginaliaSessionNoteEditor";
import { MarginaliaSessionTitleEditor } from "../../../../src/features/marginalia/sessionDetail/MarginaliaSessionTitleEditor";
import {
  marginaliaAnnotationOrderingOptions,
  MarginaliaSessionDetailPageRegion,
  MarginaliaSessionDeleteDialog,
  confirmPermanentSessionDeletion,
  permanentSessionDeletionWarning,
  orderMarginaliaAnnotations,
} from "../../../../src/features/marginalia/sessionDetail/MarginaliaSessionDetailPageRegion";
import { idleMutationState } from "../../../../src/shared/feedback/mutationState";
import { marginaliaSessionDisplayName } from "../../../../src/shared/marginaliaSessionDisplayName";

const detail: MarginaliaSessionEnvelope = {
  book: {
    id: "book/id",
    title: "Visible Book",
    authors: [{ id: "author-1", name: "Visible Author" }],
    series: { id: "series-1", name: "Visible Series", seriesIndex: "2.00" },
    coverUrl: "/media/cover.jpg",
    canOpen: true,
    sessionCount: 2,
    activeSessionCount: 1,
    lastActivityAt: "2026-01-03T00:00:00Z",
  },
  session: {
    id: "session-sensitive-id",
    name: "Imported history",
    notes: "Owned Session note",
    status: "active",
    startedAt: "2026-01-01T00:00:00Z",
    closedAt: null,
    updatedAt: "2026-01-03T00:00:00Z",
    lastActivityAt: "2026-01-03T00:00:00Z",
    annotationCount: 2,
    progress: {
      location: "epubcfi(/6/2)",
      locationLabel: "Chapter 08 · 42%",
      updatedAt: "2026-01-03T00:00:00Z",
    },
  },
};

const annotations: MarginaliaAnnotation[] = [
  {
    id: "annotation-1",
    clientId: "reader-highlight-1",
    kind: "highlight",
    location: { location: "epubcfi(/6/4)", locationLabel: "Chapter 09 · 47%" },
    body: {
      text: "Quoted passage",
      prefix: "Before ",
      suffix: " after.",
      color: "yellow",
      note: "Reader note",
    },
    createdAt: "2026-01-02T00:00:00Z",
    updatedAt: "2026-01-02T00:00:00Z",
  },
  {
    id: "annotation-2",
    clientId: "reader-bookmark-1",
    kind: "bookmark",
    location: { location: "epubcfi(/6/6)", locationLabel: "Chapter 10 · 51%" },
    createdAt: "2026-01-03T00:00:00Z",
    updatedAt: "2026-01-03T00:00:00Z",
  },
];

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
});

function renderDetail(overrides: Partial<Parameters<typeof MarginaliaSessionDetailPageRegion>[0]> = {}) {
  return renderToStaticMarkup(<MemoryRouter><MarginaliaSessionDetailPageRegion
    detail={detail}
    annotations={{ loading: false, items: annotations }}
    sessionNote={<MarginaliaSessionNoteEditor
      note={detail.session.notes}
      editable
      draft={detail.session.notes}
      editing={false}
      pending={false}
      onDraftChange={vi.fn()}
      onEdit={vi.fn()}
      onSave={vi.fn()}
      onCancel={vi.fn()}
    />}
    closeState={idleMutationState}
    deleteState={idleMutationState}
    exportState={idleMutationState}
    onClose={vi.fn()}
    onDelete={vi.fn()}
    onExport={vi.fn()}
    onRetryAnnotations={vi.fn()}
    {...overrides}
  /></MemoryRouter>);
}

describe("My Marginalia Session Detail", () => {
  it("sorts the complete annotation collection without disturbing canonical reading-order ties", () => {
    const completeCollection = Array.from({ length: 250 }, (_, index): MarginaliaAnnotation => ({
      ...annotations[index % annotations.length]!,
      id: `annotation-${index.toString().padStart(3, "0")}`,
      createdAt: new Date(Date.UTC(2026, 0, 1, 0, index % 5)).toISOString(),
    }));
    const equalTimestampIds = completeCollection
      .filter((annotation) => annotation.createdAt === completeCollection[0]!.createdAt)
      .map((annotation) => annotation.id);

    expect(orderMarginaliaAnnotations(completeCollection, "reading").map(({ id }) => id))
      .toEqual(completeCollection.map(({ id }) => id));
    const newest = orderMarginaliaAnnotations(completeCollection, "newest");
    const oldest = orderMarginaliaAnnotations(completeCollection, "oldest");
    expect(newest).toHaveLength(250);
    expect(oldest).toHaveLength(250);
    expect(Date.parse(newest[0]!.createdAt)).toBeGreaterThan(Date.parse(newest.at(-1)!.createdAt));
    expect(Date.parse(oldest[0]!.createdAt)).toBeLessThan(Date.parse(oldest.at(-1)!.createdAt));
    expect(newest.filter(({ createdAt }) => createdAt === completeCollection[0]!.createdAt).map(({ id }) => id))
      .toEqual(equalTimestampIds);
    expect(oldest.filter(({ createdAt }) => createdAt === completeCollection[0]!.createdAt).map(({ id }) => id))
      .toEqual(equalTimestampIds);
  });

  it("offers the three local annotation orderings only for sortable collections", () => {
    expect(marginaliaAnnotationOrderingOptions.map(({ value }) => value)).toEqual(["reading", "newest", "oldest"]);
    expect(renderDetail()).toContain('aria-label="Order marginalia, current: Reading order"');
    expect(renderDetail({ annotations: { loading: false, items: annotations.slice(0, 1) } })).not.toContain("Order marginalia");
    expect(renderDetail({ annotations: { loading: false, items: [] } })).not.toContain("Order marginalia");
  });

  it("keeps the detail route and consistent named or display-only fallback breadcrumbs", async () => {
    const children = appRoutes[0]?.children ?? [];
    expect(children.some((route) => "path" in route && route.path === "marginalia/sessions/:sessionId")).toBe(true);
    expect(marginaliaSessionBreadcrumbFallback(detail.session).at(-1)?.label).toBe("Imported history");

    const unnamedSession = { ...detail.session, id: "7f0c9ea5-2c36-4a84-b55b-447e57c24736", name: "" };
    expect(marginaliaSessionBreadcrumbFallback(unnamedSession).at(-1)?.label).toBe("Unnamed Reading Session c24736");
    expect(marginaliaSessionDisplayName(unnamedSession)).toBe("Unnamed Reading Session c24736");
  });

  it("keeps compact name editing keyboard behavior and active-only controls", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onSave = vi.fn();
    const onCancel = vi.fn();
    await act(async () => root?.render(<MarginaliaSessionTitleEditor
      displayName={detail.session.name}
      editable
      draft="Changed"
      editing
      pending={false}
      onDraftChange={vi.fn()}
      onEdit={vi.fn()}
      onSave={onSave}
      onCancel={onCancel}
    />));
    const input = container.querySelector<HTMLInputElement>('input[aria-label="Reading Session name"]')!;
    expect(container.querySelector('[aria-label="Save Reading Session name"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Cancel editing Reading Session name"]')).not.toBeNull();
    const enter = new KeyboardEvent("keydown", { key: "Enter", bubbles: true, cancelable: true });
    const escape = new KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true });
    await act(async () => input.dispatchEvent(enter));
    await act(async () => input.dispatchEvent(escape));
    expect(onSave).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
    expect(enter.defaultPrevented).toBe(true);
    expect(escape.defaultPrevented).toBe(true);

    const closedMarkup = renderToStaticMarkup(MarginaliaSessionTitleEditor({
      displayName: "Closed", editable: false, draft: "", editing: false, pending: false,
      onDraftChange: vi.fn(), onEdit: vi.fn(), onSave: vi.fn(), onCancel: vi.fn(),
    }));
    expect(closedMarkup).not.toContain("Edit Reading Session name");
  });

  it("keeps Session Note save explicit inside the mounted textarea", async () => {
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    const onSave = vi.fn();
    const onCancel = vi.fn();
    await act(async () => root?.render(<MarginaliaSessionNoteEditor
      note={detail.session.notes}
      editable
      draft="Edited note"
      editing
      pending={false}
      onDraftChange={vi.fn()}
      onEdit={vi.fn()}
      onSave={onSave}
      onCancel={onCancel}
    />));
    const textarea = container.querySelector<HTMLTextAreaElement>('textarea[aria-label="Reading Session note"]')!;
    expect(container.querySelector('[aria-label="Save Reading Session note"]')).not.toBeNull();
    await act(async () => textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true })));
    expect(onSave).not.toHaveBeenCalled();
    await act(async () => textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", ctrlKey: true, bubbles: true })));
    await act(async () => textarea.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true })));
    expect(onSave).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("renders only selected quote text while keeping notes separate and locator internals hidden", () => {
    const markup = renderDetail();
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("Visible Author");
    expect(markup).toContain("Visible Series 2.0");
    expect(markup).toContain("Chapter 08 · 42%");
    expect(markup).toContain("Chapter 09 · 47%");
    expect(markup).toContain("Quoted passage");
    expect(markup).not.toContain("Before ");
    expect(markup).not.toContain(" after.");
    expect(markup).toContain("Reader note");
    expect(markup).toContain("Chapter 10 · 51%");
    expect(markup).toContain('href="/library/books/book%2Fid"');
    expect(markup).toContain('href="/marginalia?view=books&amp;book=book%2Fid"');
    expect(markup.match(/Quoted passage/g)).toHaveLength(1);
    expect(markup.indexOf("Quoted passage")).toBeLessThan(markup.indexOf("Chapter 10 · 51%"));
    for (const internal of ["epubcfi", "reader-highlight-1", "reader-bookmark-1", "annotation-1", "annotation-2"]) {
      expect(markup).not.toContain(internal);
    }
  });

  it("keeps quote whitespace confined to selected text for closed historical Sessions", () => {
    const selectedText = "  Quoted\npassage  ";
    const highlight = {
      ...annotations[0]!,
      kind: "highlight" as const,
      body: { text: selectedText, prefix: "ANCHOR BEFORE", suffix: "ANCHOR AFTER", color: "yellow" as const, note: "Reader note" },
    };
    const markup = renderDetail({
      detail: { ...detail, session: { ...detail.session, status: "closed", closedAt: "2026-01-04T00:00:00Z" } },
      annotations: { loading: false, items: [highlight] },
    });

    expect(markup).toContain(selectedText);
    expect(markup).not.toContain("ANCHOR BEFORE");
    expect(markup).not.toContain("ANCHOR AFTER");
    expect(markup).toContain("Reader note");
  });

  it("shows null progress safely and gates only Library Book navigation through canOpen", () => {
    const unavailableDetail = {
      book: { ...detail.book, title: "Owned historical Book", coverUrl: "/media/history.jpg", canOpen: false },
      session: { ...detail.session, progress: null },
    };
    const markup = renderDetail({ detail: unavailableDetail });
    expect(markup).toContain("Owned historical Book");
    expect(markup).toContain("/media/history.jpg");
    expect(markup).toContain("No saved progress");
    expect(markup).not.toContain('/library/books/');
    expect(markup).toContain('/marginalia?view=books&amp;book=book%2Fid');
  });

  it("shows close only for active Sessions and retains delete for closed history", async () => {
    const onClose = vi.fn();
    const activeMarkup = renderDetail({ onClose });
    expect(activeMarkup).toContain("Close Reading Session");
    expect(activeMarkup.indexOf("Active")).toBeLessThan(activeMarkup.indexOf("Close Reading Session"));
    expect(activeMarkup.indexOf("Close Reading Session")).toBeLessThan(activeMarkup.indexOf("Delete"));
    expect(activeMarkup).toContain(">close</span>Close Reading Session");
    expect(activeMarkup).toContain(">delete</span>Delete");

    const closed = {
      ...detail,
      session: { ...detail.session, status: "closed" as const, closedAt: "2026-01-04T00:00:00Z" },
    };
    const closedMarkup = renderDetail({
      detail: closed,
      sessionNote: <MarginaliaSessionNoteEditor
        note={closed.session.notes} editable={false} draft="" editing={false} pending={false}
        onDraftChange={vi.fn()} onEdit={vi.fn()} onSave={vi.fn()} onCancel={vi.fn()}
      />,
    });
    expect(closedMarkup).toContain("Closed");
    expect(closedMarkup).toContain(">delete</span>Delete");
    expect(closedMarkup).not.toContain("Close Reading Session");
    expect(closedMarkup).not.toContain("Edit Reading Session note");
  });

  it("requires the native final confirmation after the application confirmation", () => {
    const confirm = vi.fn().mockReturnValue(false);
    const remove = vi.fn();
    expect(confirmPermanentSessionDeletion(remove, confirm)).toBe(false);
    expect(confirm).toHaveBeenCalledOnce();
    expect(confirm).toHaveBeenCalledWith(permanentSessionDeletionWarning);
    expect(remove).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    expect(confirmPermanentSessionDeletion(remove, confirm)).toBe(true);
    expect(confirm).toHaveBeenCalledTimes(2);
    expect(remove).toHaveBeenCalledOnce();
  });

  it("presents an accessible application confirmation with bounded Session and Book context", () => {
    const markup = renderToStaticMarkup(<MarginaliaSessionDeleteDialog
      sessionName={detail.session.name}
      bookTitle={detail.book.title}
      pending={false}
      exportState={idleMutationState}
      onCancel={vi.fn()}
      onContinue={vi.fn()}
      onExport={vi.fn()}
    />);
    expect(markup).toContain('role="dialog"');
    expect(markup).toContain('aria-modal="true"');
    expect(markup).toContain("Delete this Reading Session?");
    expect(markup).toContain("Imported history");
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("all Marginalia in it");
    expect(markup).toContain("This cannot be undone.");
    expect(markup).toContain("Cancel");
    expect(markup).toContain(">Continue</button>");
    expect(markup).toContain(">download</span>Export Reading Session");
  });

  it("keeps export feedback independent and blocks overlapping export and deletion progression", () => {
    const exporting = renderToStaticMarkup(<MarginaliaSessionDeleteDialog
      sessionName={detail.session.name}
      bookTitle={detail.book.title}
      pending={false}
      exportState={{ pending: true }}
      onCancel={vi.fn()}
      onContinue={vi.fn()}
      onExport={vi.fn()}
    />);
    expect(exporting).toContain("Exporting…");
    expect(exporting.match(/disabled=""/g)).toHaveLength(2);
    expect(exporting).not.toMatch(/disabled=""[^>]*>Cancel/);

    const failed = renderToStaticMarkup(<MarginaliaSessionDeleteDialog
      sessionName={detail.session.name}
      bookTitle={detail.book.title}
      pending={false}
      exportState={{ pending: false, error: new Error("Archive unavailable") }}
      onCancel={vi.fn()}
      onContinue={vi.fn()}
      onExport={vi.fn()}
    />);
    expect(failed).toContain("Archive unavailable");
    expect(failed).toContain("Export Reading Session");
    expect(failed).toContain("Cancel");
    expect(failed).toContain(">Continue</button>");

    const deleting = renderToStaticMarkup(<MarginaliaSessionDeleteDialog
      sessionName={detail.session.name}
      bookTitle={detail.book.title}
      pending
      exportState={idleMutationState}
      onCancel={vi.fn()}
      onContinue={vi.fn()}
      onExport={vi.fn()}
    />);
    expect(deleting).toMatch(/disabled=""[^>]*><span[^>]*>download<\/span>Export Reading Session/);
  });

  it("disables both lifecycle controls and shows bounded feedback while deletion is pending or failed", () => {
    const pending = renderDetail({ deleteState: { pending: true } });
    expect(pending).toContain("Deleting…");
    expect(pending.match(/disabled=""/g)).toHaveLength(2);

    const failed = renderDetail({ deleteState: { pending: false, error: new Error("Session deletion failed") } });
    expect(failed).toContain("Session deletion failed");
    expect(failed).toContain("Close Reading Session");
    expect(failed).toContain(">delete</span>Delete");
  });

  it("keeps annotation and close failures bounded without discarding loaded content", () => {
    const markup = renderDetail({
      annotations: { loading: false, items: annotations, error: new Error("Annotations unavailable") },
      closeState: { pending: false, error: new Error("Session changed elsewhere") },
    });
    expect(markup).toContain("Annotations unavailable");
    expect(markup).toContain("Session changed elsewhere");
    expect(markup).toContain("Quoted passage");
    expect(markup).toContain("Close Reading Session");
  });

  it("preserves annotation loading and empty states without client pagination controls", () => {
    expect(renderDetail({ annotations: { loading: true } })).toContain("Loading marginalia...");
    const empty = renderDetail({ annotations: { loading: false, items: [] } });
    expect(empty).toContain("No marginalia found.");
    expect(empty).not.toContain("Order marginalia");
    expect(empty).not.toContain("Page size");
  });
});
