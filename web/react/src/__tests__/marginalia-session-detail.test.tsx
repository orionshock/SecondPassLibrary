import type { Page, ReadingAnnotation, ReadingSessionDetail } from "@second-pass/spl-api";
import { Children, type ReactElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { appRoutes } from "../app/router";
import { marginaliaSessionBreadcrumbFallback } from "../features/marginalia/marginaliaBreadcrumbs";
import { renameMarginaliaSession, updateMarginaliaSessionNote } from "../features/marginalia/MarginaliaSessionDetailOrchestrator";
import { MarginaliaSessionNoteEditorComponent } from "../features/marginalia/components/MarginaliaSessionNoteEditorComponent";
import { MarginaliaSessionTitleEditorComponent } from "../features/marginalia/components/MarginaliaSessionTitleEditorComponent";
import { AnnotationCategoryMenuOptionsComponent, MarginaliaSessionDetailPageRegion, annotationOrderOptions } from "../features/marginalia/regions/MarginaliaSessionDetailPageRegion";
import { OrderMenuOptionsComponent } from "../shared/forms/OrderMenuComponent";

const session: ReadingSessionDetail = {
  id: "session-sensitive-id",
  name: "Imported history",
  status: "completed",
  isActive: false,
  startedAt: "2026-01-01T00:00:00Z",
  completedAt: "2026-01-03T00:00:00Z",
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-03T00:00:00Z",
  notes: "Owned Session note",
  progression: 0.5,
  annotationCount: 2,
  canOpen: true,
  book: {
    id: "book/id",
    title: "Visible Book",
    authors: [{ id: "author-1", name: "Visible Author" }],
    series: { id: "series-1", name: "Visible Series" },
    seriesIndex: "2.0",
    coverUrl: "/media/cover.jpg",
    unavailable: false,
  },
};

const annotations: Page<ReadingAnnotation> = {
  count: 2,
  next: null,
  previous: null,
  items: [
    { id: "annotation-1", kind: "highlight", highlightText: "Quoted passage", highlightColor: "yellow", commentText: "Reader note", hasComment: true, createdAt: "2026-01-02T00:00:00Z", updatedAt: "2026-01-02T00:00:00Z", selector: "epubcfi(/6/2)", xpath: "/html/body" } as ReadingAnnotation,
    { id: "annotation-2", kind: "bookmark", highlightText: "", highlightColor: "", commentText: "", hasComment: false, createdAt: "2026-01-03T00:00:00Z", updatedAt: "2026-01-03T00:00:00Z" },
  ],
};

function renderDetail(overrides: Partial<Parameters<typeof MarginaliaSessionDetailPageRegion>[0]> = {}) {
  return renderToStaticMarkup(<MemoryRouter><MarginaliaSessionDetailPageRegion
    session={session}
    progress={{ loading: false, progress: { sessionId: session.id, progression: 0.5, createdAt: null, updatedAt: "2026-01-03T00:00:00Z" } }}
    annotations={{ loading: false, page: annotations }}
    sessionNote={<MarginaliaSessionNoteEditorComponent
      note={session.notes}
      editable={false}
      draft={session.notes}
      editing={false}
      pending={false}
      onDraftChange={vi.fn()}
      onEdit={vi.fn()}
      onSave={vi.fn()}
      onCancel={vi.fn()}
    />}
    annotationCategories={["highlight", "highlightWithNote"]}
    annotationOrder="newest"
    pageNumber={1}
    pageSize={20}
    onAnnotationCategoriesChange={vi.fn()}
    onAnnotationOrderChange={vi.fn()}
    onPageChange={vi.fn()}
    onPageSizeChange={vi.fn()}
    onRetryProgress={vi.fn()}
    onRetryAnnotations={vi.fn()}
    {...overrides}
  /></MemoryRouter>);
}

describe("My Marginalia Session Detail", () => {
  it("registers the detail route and builds a bounded breadcrumb without Session IDs", () => {
    const children = appRoutes[0]?.children ?? [];
    expect(children.some((route) => "path" in route && route.path === "marginalia/sessions/:sessionId")).toBe(true);
    expect(marginaliaSessionBreadcrumbFallback("Imported history")).toEqual([{ label: "My Marginalia", to: "/marginalia", resetTrail: true }, { label: "Imported history" }]);
    expect(JSON.stringify(marginaliaSessionBreadcrumbFallback(""))).not.toContain(session.id);
  });

  it("exposes compact Session-name edit, save, cancel, and keyboard controls", () => {
    const onEdit = vi.fn();
    const onSave = vi.fn();
    const onCancel = vi.fn();
    const onDraftChange = vi.fn();
    const resting = MarginaliaSessionTitleEditorComponent({
      displayName: "Imported history", editable: true, draft: "Imported history", editing: false, pending: false,
      onDraftChange, onEdit, onSave, onCancel,
    }) as ReactElement<{ children: unknown }>;
    const restingMarkup = renderToStaticMarkup(resting);
    expect(restingMarkup).toContain('aria-label="Edit session name"');
    const restingChildren = Children.toArray(resting.props.children as ReactNode) as ReactElement<{ onClick?: () => void }>[];
    restingChildren.at(-1)?.props.onClick?.();
    expect(onEdit).toHaveBeenCalledOnce();

    const editing = MarginaliaSessionTitleEditorComponent({
      displayName: "Imported history", editable: true, draft: "Changed name", editing: true, pending: false,
      onDraftChange, onEdit, onSave, onCancel,
    }) as ReactElement<{ children: unknown }>;
    const editingMarkup = renderToStaticMarkup(editing);
    expect(editingMarkup).toContain('aria-label="Session name"');
    expect(editingMarkup).toContain('aria-label="Save session name"');
    expect(editingMarkup).toContain('aria-label="Cancel editing session name"');
    const input = Children.toArray(editing.props.children as ReactNode)[0] as ReactElement<{ onKeyDown: (event: { key: string; preventDefault: () => void }) => void }>;
    input.props.onKeyDown({ key: "Enter", preventDefault: vi.fn() });
    input.props.onKeyDown({ key: "Escape", preventDefault: vi.fn() });
    expect(onSave).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();

    const historical = renderToStaticMarkup(MarginaliaSessionTitleEditorComponent({
      displayName: "Historical Session", editable: false, draft: "", editing: false, pending: false,
      onDraftChange, onEdit, onSave, onCancel,
    }));
    expect(historical).not.toContain("Edit session name");
  });

  it("skips unchanged names and delegates changed names without hiding update errors", async () => {
    const update = vi.fn().mockResolvedValue({ ...session, name: "Renamed history" });

    await expect(renameMarginaliaSession(session, ` ${session.name} `, update)).resolves.toEqual({ session, changed: false });
    expect(update).not.toHaveBeenCalled();

    await expect(renameMarginaliaSession(session, "  Renamed history  ", update)).resolves.toMatchObject({
      changed: true,
      session: { name: "Renamed history" },
    });
    expect(update).toHaveBeenCalledWith(session.id, { name: "Renamed history" });

    const error = new Error("Rename failed");
    await expect(renameMarginaliaSession(session, "Another name", vi.fn().mockRejectedValue(error))).rejects.toBe(error);
  });

  it("edits active Session notes with textarea-safe keyboard controls", () => {
    const onSave = vi.fn();
    const onCancel = vi.fn();
    const editor = MarginaliaSessionNoteEditorComponent({
      note: "Current note", editable: true, draft: "Changed note", editing: true, pending: false,
      onDraftChange: vi.fn(), onEdit: vi.fn(), onSave, onCancel,
    }) as ReactElement<{ children: ReactNode }>;
    const markup = renderToStaticMarkup(editor);
    expect(markup).toContain('aria-label="Session Note"');
    expect(markup).toContain('aria-label="Save session note"');
    expect(markup).toContain('aria-label="Cancel editing session note"');
    const textarea = Children.toArray(editor.props.children)[1] as ReactElement<{ onKeyDown: (event: { key: string; ctrlKey?: boolean; metaKey?: boolean; preventDefault: () => void }) => void }>;
    textarea.props.onKeyDown({ key: "Enter", preventDefault: vi.fn() });
    expect(onSave).not.toHaveBeenCalled();
    textarea.props.onKeyDown({ key: "Enter", ctrlKey: true, preventDefault: vi.fn() });
    textarea.props.onKeyDown({ key: "Escape", preventDefault: vi.fn() });
    expect(onSave).toHaveBeenCalledOnce();
    expect(onCancel).toHaveBeenCalledOnce();
  });

  it("keeps historical notes read-only and omits the duplicated Session title", () => {
    const markup = renderDetail();
    expect(markup).toContain("Owned Session note");
    expect(markup).not.toContain('aria-label="Edit session note"');
    expect(markup).not.toContain(session.name);
  });

  it("skips unchanged notes, saves changed notes, and preserves update errors", async () => {
    const update = vi.fn().mockResolvedValue({ ...session, notes: "Changed note" });
    await expect(updateMarginaliaSessionNote(session, ` ${session.notes} `, update)).resolves.toEqual({ session, changed: false });
    expect(update).not.toHaveBeenCalled();
    await expect(updateMarginaliaSessionNote(session, "  Changed note  ", update)).resolves.toMatchObject({ changed: true, session: { notes: "Changed note" } });
    expect(update).toHaveBeenCalledWith(session.id, { notes: "Changed note" });
    const error = new Error("Note update failed");
    await expect(updateMarginaliaSessionNote(session, "Another note", vi.fn().mockRejectedValue(error))).rejects.toBe(error);
  });

  it("renders visible Book, progress, and annotation content without locator internals", () => {
    const markup = renderDetail();
    for (const value of ["Visible Book", "Visible Author", "Visible Series", "Owned Session note", "Quoted passage", "Reader note"]) expect(markup).toContain(value);
    expect(markup).toContain('href="/library/books/book%2Fid"');
    expect(markup).toContain("50%");
    expect(markup).toContain('aria-label="Reading progress"');
    expect(markup).not.toContain("epubcfi");
    expect(markup).not.toContain("/html/body");
    expect(markup).not.toContain("session-sensitive-id");
    expect(markup).not.toContain("Open in Reader");
  });

  it("keeps unavailable Book history inspectable without exposing a Book destination", () => {
    const unavailable = { ...session, canOpen: false, book: { id: null, title: "", authors: [], series: null, seriesIndex: null, coverUrl: null, unavailable: true } };
    const markup = renderDetail({ session: unavailable });
    expect(markup).toContain("Owned Session note");
    expect(markup).not.toContain('href="/library/books/');
    expect(markup).not.toContain("book/id");
  });

  it("keeps annotation failures bounded while retaining Session content", () => {
    const markup = renderDetail({ annotations: { loading: false, error: new Error("Annotation load failed") } });
    expect(markup).toContain("Owned Session note");
    expect(markup).toContain('role="alert"');
    expect(markup).toContain("Annotation load failed");
  });

  it("renders the no-percentage state and keeps progress failures local to the summary", () => {
    const unavailableProgress = renderDetail({ progress: { loading: false, progress: { sessionId: session.id, progression: null, createdAt: null, updatedAt: null } } });
    expect(unavailableProgress).toContain('aria-label="Progress unavailable"');
    expect(unavailableProgress).not.toContain("NaN");

    const failed = renderDetail({ progress: { loading: false, error: new Error("Progress load failed") } });
    expect(failed).toContain("Owned Session note");
    expect(failed).toContain('role="alert"');
    expect(failed).toContain("Progress load failed");
  });

  it("renders annotation controls and paginated-list contracts", () => {
    const markup = renderDetail({ annotations: { loading: false, page: { ...annotations, count: 40, next: "/next" } } });
    expect(markup).toContain('aria-label="Show marginalia, current: Highlights"');
    const orderMarkup = renderToStaticMarkup(<OrderMenuOptionsComponent value="newest" options={annotationOrderOptions} ariaLabel="Order marginalia" onSelect={vi.fn()} />);
    expect((orderMarkup.match(/role="menuitem"/g) ?? [])).toHaveLength(4);
    expect(markup).toContain('aria-label="Marginalia pagination, top"');
    expect(markup).toContain('aria-label="Marginalia pagination, bottom"');
  });

  it("supports disjoint multi-category selections without deselecting the final category", () => {
    const onChange = vi.fn();
    const menu = AnnotationCategoryMenuOptionsComponent({ value: ["bookmark", "highlightWithNote"], onChange });
    const options = (menu as ReactElement<{ children: ReactElement<{ onClick: () => void }>[] }>).props.children;
    options[1]!.props.onClick();
    expect(onChange).toHaveBeenCalledWith(["bookmark", "highlight", "highlightWithNote"]);

    const single = AnnotationCategoryMenuOptionsComponent({ value: ["bookmark"], onChange: vi.fn() });
    const singleOptions = (single as ReactElement<{ children: ReactElement<{ disabled?: boolean }>[] }>).props.children;
    expect(singleOptions[0]!.props.disabled).toBe(true);
  });
});
