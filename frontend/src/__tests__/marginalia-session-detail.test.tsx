import type { MarginaliaAnnotation, MarginaliaSessionEnvelope } from "@second-pass/spl-api";
import { Children, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { appRoutes } from "../app/router";
import { marginaliaSessionBreadcrumbFallback } from "../features/marginalia/marginaliaBreadcrumbs";
import {
  closeMarginaliaSessionFromProductUi,
  deleteMarginaliaSessionFromProductUi,
  exportMarginaliaSessionFromProductUi,
  renameMarginaliaSession,
  updateMarginaliaSessionNote,
} from "../features/marginalia/MarginaliaSessionDetailOrchestrator";
import { MarginaliaSessionNoteEditorComponent } from "../features/marginalia/components/MarginaliaSessionNoteEditorComponent";
import { MarginaliaSessionTitleEditorComponent } from "../features/marginalia/components/MarginaliaSessionTitleEditorComponent";
import {
  marginaliaAnnotationOrderingOptions,
  MarginaliaSessionDetailPageRegion,
  MarginaliaSessionDeleteDialog,
  confirmPermanentSessionDeletion,
  permanentSessionDeletionWarning,
  orderMarginaliaAnnotations,
} from "../features/marginalia/regions/MarginaliaSessionDetailPageRegion";
import { idleMutationState } from "../shared/feedback/mutationState";
import { marginaliaSessionDisplayName } from "../shared/marginaliaSessionDisplayName";

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
      cfi: "epubcfi(/6/2)",
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
    location: { cfi: "epubcfi(/6/4)", locationLabel: "Chapter 09 · 47%" },
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
    location: { cfi: "epubcfi(/6/6)", locationLabel: "Chapter 10 · 51%" },
    createdAt: "2026-01-03T00:00:00Z",
    updatedAt: "2026-01-03T00:00:00Z",
  },
];

function renderDetail(overrides: Partial<Parameters<typeof MarginaliaSessionDetailPageRegion>[0]> = {}) {
  return renderToStaticMarkup(<MemoryRouter><MarginaliaSessionDetailPageRegion
    detail={detail}
    annotations={{ loading: false, items: annotations }}
    sessionNote={<MarginaliaSessionNoteEditorComponent
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
    const unnamedDetail = { ...detail, session: unnamedSession };
    expect(marginaliaSessionBreadcrumbFallback(unnamedSession).at(-1)?.label).toBe("Unnamed Session c24736");
    expect(marginaliaSessionDisplayName(unnamedSession)).toBe("Unnamed Session c24736");

    const update = vi.fn();
    await expect(renameMarginaliaSession(unnamedDetail, "", update)).resolves.toEqual({ detail: unnamedDetail, changed: false });
    expect(update).not.toHaveBeenCalled();
  });

  it("keeps compact name editing keyboard behavior and active-only controls", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    const editor = MarginaliaSessionTitleEditorComponent({
      displayName: detail.session.name, editable: true, draft: "Changed", editing: true, pending: false,
      onDraftChange: vi.fn(), onEdit: vi.fn(), onSave, onCancel,
    }) as ReactElement<{ children: unknown }>;
    const markup = renderToStaticMarkup(editor);
    expect(markup).toContain('aria-label="Session name"');
    expect(markup).toContain('aria-label="Save session name"');
    expect(markup).toContain('aria-label="Cancel editing session name"');
    const input = Children.toArray(editor.props.children as ReactNode)[0] as ReactElement<{ onKeyDown: (event: { key: string; preventDefault: () => void }) => void }>;
    input.props.onKeyDown({ key: "Enter", preventDefault: vi.fn() });
    input.props.onKeyDown({ key: "Escape", preventDefault: vi.fn() });
    expect(onSave).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();

    const closedMarkup = renderToStaticMarkup(MarginaliaSessionTitleEditorComponent({
      displayName: "Closed", editable: false, draft: "", editing: false, pending: false,
      onDraftChange: vi.fn(), onEdit: vi.fn(), onSave: vi.fn(), onCancel: vi.fn(),
    }));
    expect(closedMarkup).not.toContain("Edit session name");
  });

  it("updates active names and notes through the canonical detail envelope", async () => {
    const renamed = { ...detail, session: { ...detail.session, name: "Renamed" } };
    const rename = vi.fn().mockResolvedValue(renamed);
    await expect(renameMarginaliaSession(detail, " Renamed ", rename)).resolves.toEqual({ detail: renamed, changed: true });
    expect(rename).toHaveBeenCalledWith(detail.session.id, { name: "Renamed" });

    const noted = { ...renamed, session: { ...renamed.session, notes: "New note" } };
    const updateNote = vi.fn().mockResolvedValue(noted);
    await expect(updateMarginaliaSessionNote(renamed, " New note ", updateNote)).resolves.toEqual({ detail: noted, changed: true });
    expect(updateNote).toHaveBeenCalledWith(detail.session.id, { notes: "New note" });
  });

  it("keeps Session Note save explicit inside the textarea", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    const editor = MarginaliaSessionNoteEditorComponent({
      note: detail.session.notes,
      editable: true,
      draft: "Edited note",
      editing: true,
      pending: false,
      onDraftChange: vi.fn(),
      onEdit: vi.fn(),
      onSave,
      onCancel,
    }) as ReactElement<{ children: unknown }>;
    const markup = renderToStaticMarkup(editor);
    expect(markup).toContain('aria-label="Session Note"');
    expect(markup).toContain('aria-label="Save session note"');
    const textarea = Children.toArray(editor.props.children as ReactNode)[1] as ReactElement<{
      onKeyDown: (event: { key: string; ctrlKey?: boolean; metaKey?: boolean; preventDefault: () => void }) => void;
    }>;
    textarea.props.onKeyDown({ key: "Enter", preventDefault: vi.fn() });
    expect(onSave).not.toHaveBeenCalled();
    textarea.props.onKeyDown({ key: "Enter", ctrlKey: true, preventDefault: vi.fn() });
    textarea.props.onKeyDown({ key: "Escape", preventDefault: vi.fn() });
    expect(onSave).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("renders canonical Book context, progress, and the complete annotation union without locator internals", () => {
    const markup = renderDetail();
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("Visible Author");
    expect(markup).toContain("Visible Series 2.0");
    expect(markup).toContain("Chapter 08 · 42%");
    expect(markup).toContain("Chapter 09 · 47%");
    expect(markup).toContain("Before ");
    expect(markup).toContain("Quoted passage");
    expect(markup).toContain(" after.");
    expect(markup).toContain("Reader note");
    expect(markup).toContain("Chapter 10 · 51%");
    expect(markup.match(/Quoted passage/g)).toHaveLength(1);
    expect(markup.indexOf("Quoted passage")).toBeLessThan(markup.indexOf("Chapter 10 · 51%"));
    for (const internal of ["epubcfi", "reader-highlight-1", "reader-bookmark-1", "annotation-1", "annotation-2"]) {
      expect(markup).not.toContain(internal);
    }
  });

  it("shows null progress safely and gates View Book only through canOpen", () => {
    const unavailableDetail = {
      book: { ...detail.book, title: "Owned historical Book", coverUrl: "/media/history.jpg", canOpen: false },
      session: { ...detail.session, progress: null },
    };
    const markup = renderDetail({ detail: unavailableDetail });
    expect(markup).toContain("Owned historical Book");
    expect(markup).toContain("/media/history.jpg");
    expect(markup).toContain("No saved progress");
    expect(markup).not.toContain("View Book");
  });

  it("closes only active Sessions and replaces the page with the authoritative closed detail", async () => {
    const onClose = vi.fn();
    const activeMarkup = renderDetail({ onClose });
    expect(activeMarkup).toContain("Close Session");
    expect(activeMarkup.indexOf("Active")).toBeLessThan(activeMarkup.indexOf("Close Session"));
    expect(activeMarkup.indexOf("Close Session")).toBeLessThan(activeMarkup.indexOf("Delete"));
    expect(activeMarkup).toContain(">close</span>Close Session");
    expect(activeMarkup).toContain(">delete</span>Delete");

    const closed = {
      ...detail,
      session: { ...detail.session, status: "closed" as const, closedAt: "2026-01-04T00:00:00Z" },
    };
    const close = vi.fn().mockResolvedValue(closed);
    await expect(closeMarginaliaSessionFromProductUi(detail, close)).resolves.toBe(closed);
    expect(close).toHaveBeenCalledWith(detail.session.id);

    const closedMarkup = renderDetail({
      detail: closed,
      sessionNote: <MarginaliaSessionNoteEditorComponent
        note={closed.session.notes} editable={false} draft="" editing={false} pending={false}
        onDraftChange={vi.fn()} onEdit={vi.fn()} onSave={vi.fn()} onCancel={vi.fn()}
      />,
    });
    expect(closedMarkup).toContain("Closed");
    expect(closedMarkup).toContain(">delete</span>Delete");
    expect(closedMarkup).not.toContain("Close Session");
    expect(closedMarkup).not.toContain("Edit session note");
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
    expect(markup).toContain("Delete this reading session?");
    expect(markup).toContain("Imported history");
    expect(markup).toContain("Visible Book");
    expect(markup).toContain("all annotations attached to it");
    expect(markup).toContain("This cannot be undone.");
    expect(markup).toContain("Cancel");
    expect(markup).toContain("Continue to delete");
    expect(markup).toContain(">download</span>Export Session");
  });

  it("uses the selected-Session archive and existing browser download path for exactly the current Session", async () => {
    const attachment = { blob: new Blob(["archive"]), filename: "20260812-second-pass-marginalia.json" };
    const download = vi.fn().mockResolvedValue(attachment);
    const save = vi.fn();

    await expect(exportMarginaliaSessionFromProductUi(detail.session.id, download, save)).resolves.toBeUndefined();

    expect(download).toHaveBeenCalledOnce();
    expect(download).toHaveBeenCalledWith({
      readingSessionIds: [detail.session.id],
      includeEmptySessions: true,
    });
    expect(save).toHaveBeenCalledOnce();
    expect(save).toHaveBeenCalledWith(attachment);
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
    expect(failed).toContain("Export Session");
    expect(failed).toContain("Cancel");
    expect(failed).toContain("Continue to delete");

    const deleting = renderToStaticMarkup(<MarginaliaSessionDeleteDialog
      sessionName={detail.session.name}
      bookTitle={detail.book.title}
      pending
      exportState={idleMutationState}
      onCancel={vi.fn()}
      onContinue={vi.fn()}
      onExport={vi.fn()}
    />);
    expect(deleting).toMatch(/disabled=""[^>]*><span[^>]*>download<\/span>Export Session/);
  });

  it("deletes exactly one Session and navigates only after SDK success", async () => {
    const remove = vi.fn().mockResolvedValue(undefined);
    const navigate = vi.fn();
    await expect(deleteMarginaliaSessionFromProductUi(detail.session.id, navigate, remove)).resolves.toBeUndefined();
    expect(remove).toHaveBeenCalledOnce();
    expect(remove).toHaveBeenCalledWith(detail.session.id);
    expect(navigate).toHaveBeenCalledOnce();
    expect(navigate).toHaveBeenCalledWith("/marginalia", { replace: true });

    const failure = new Error("Deletion failed");
    remove.mockRejectedValueOnce(failure);
    navigate.mockClear();
    await expect(deleteMarginaliaSessionFromProductUi(detail.session.id, navigate, remove)).rejects.toBe(failure);
    expect(navigate).not.toHaveBeenCalled();
  });

  it("disables both lifecycle controls and shows bounded feedback while deletion is pending or failed", () => {
    const pending = renderDetail({ deleteState: { pending: true } });
    expect(pending).toContain("Deleting…");
    expect(pending.match(/disabled=""/g)).toHaveLength(2);

    const failed = renderDetail({ deleteState: { pending: false, error: new Error("Session deletion failed") } });
    expect(failed).toContain("Session deletion failed");
    expect(failed).toContain("Close Session");
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
    expect(markup).toContain("Close Session");
  });

  it("preserves annotation loading and empty states without client pagination controls", () => {
    expect(renderDetail({ annotations: { loading: true } })).toContain("Loading marginalia...");
    const empty = renderDetail({ annotations: { loading: false, items: [] } });
    expect(empty).toContain("No marginalia found.");
    expect(empty).not.toContain("Order marginalia");
    expect(empty).not.toContain("Page size");
  });
});
