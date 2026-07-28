import type { CurrentUser, ReadingImportPreview, ReadingImportResult, ServerInfo } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { marginaliaImportBreadcrumbFallback } from "../features/marginalia/marginaliaBreadcrumbs";
import { MarginaliaImportOrchestrator, previewSelectedMarginaliaImport } from "../features/marginalia/MarginaliaImportOrchestrator";
import { MarginaliaSessionsOrchestrator } from "../features/marginalia/MarginaliaSessionsOrchestrator";
import { AppFrame } from "../app/layout/AppFrame";
import { buildMarginaliaImportApplyInput, createMarginaliaImportDraft, marginaliaImportBookSelectionState, marginaliaImportSelectedCount, marginaliaImportSessionKey, withMarginaliaImportBookSelection } from "../features/marginalia/marginaliaImportDraft";
import { MarginaliaImportPageRegion } from "../features/marginalia/regions/MarginaliaImportPageRegion";
import { LocalValidationError } from "../shared/feedback/mutationState";

const preview: ReadingImportPreview = {
  importToken: "opaque-token",
  valid: true,
  canApply: true,
  summary: { books: 2, sessions: 3, annotations: 5 },
  warnings: ["Active exported sessions will be imported as historical sessions."],
  unmatchedEntries: 1,
  unmatchedDownloadAvailable: true,
  books: [
    {
      title: "Matched Book", authors: ["Author One"], selectionReference: { source: "book:source", fileHash: "sha256:hidden", title: "Matched Book" },
      sessionCount: 2, annotationCount: 5, matchStatus: "matched", matchedBookTitle: "Matched Book", coverUrl: "/media/cover.jpg", willImport: true, warning: "",
      sessions: [
        { exportSessionId: "export-session-1", name: "Imported session", notes: "Remember this.", status: "active", startedAt: null, completedAt: null, annotationCount: 3, bookmarkCount: 1, highlightCount: 2, commentedHighlightCount: 1, willImport: true, needsReader: false, activeWillImportAsHistorical: true, possibleDuplicate: false, warning: "" },
        { exportSessionId: "export-session-2", name: "", notes: "", status: "completed", startedAt: null, completedAt: null, annotationCount: 2, bookmarkCount: 1, highlightCount: 1, commentedHighlightCount: 0, willImport: true, needsReader: false, activeWillImportAsHistorical: false, possibleDuplicate: true, warning: "Possible duplicate session." },
      ],
    },
    {
      title: "Missing Book", authors: [], selectionReference: { source: "book:missing", fileHash: "sha256:missing", title: "Missing Book" },
      sessionCount: 1, annotationCount: 0, matchStatus: "unmatched", matchedBookTitle: null, coverUrl: null, willImport: false, warning: "No visible local book matched this export book.",
      sessions: [{ exportSessionId: "export-session-hidden", name: "Unavailable", notes: "", status: "completed", startedAt: null, completedAt: null, annotationCount: 0, bookmarkCount: 0, highlightCount: 0, commentedHighlightCount: 0, willImport: false, needsReader: false, activeWillImportAsHistorical: false, possibleDuplicate: false, warning: "" }],
    },
  ],
};

const user: CurrentUser = { username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader", mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, readingClientBaseUrl: null, publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderImport(options: { preview?: ReadingImportPreview; result?: ReadingImportResult; draft?: ReturnType<typeof createMarginaliaImportDraft>; previewError?: Error; editingSessionKeys?: ReadonlySet<string> } = {}) {
  return renderToStaticMarkup(<MemoryRouter><MarginaliaImportPageRegion
    preview={options.preview}
    result={options.result}
    draft={options.draft ?? {}}
    editingSessionKeys={options.editingSessionKeys ?? new Set()}
    previewState={{ pending: false, error: options.previewError }}
    applyState={{ pending: false }}
    inputRef={{ current: null }}
    onFileChange={vi.fn()}
    onPreview={vi.fn()}
    onDraftChange={vi.fn()}
    onBookSelectionChange={vi.fn()}
    onEditingChange={vi.fn()}
    onApply={vi.fn()}
  /></MemoryRouter>);
}

describe("My Marginalia import", () => {
  it("links the Session list to the implemented Import route and renders that route", () => {
    const listMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/marginalia"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="marginalia" element={<MarginaliaSessionsOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(listMarkup).toContain("<h1>My Marginalia</h1>");
    expect(listMarkup).toContain('aria-label="My Marginalia sections"');
    expect(listMarkup).toContain('href="/marginalia/import"');
    const importMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/marginalia/import"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="marginalia/import" element={<MarginaliaImportOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(importMarkup).toContain("<h1>Import Marginalia</h1>");
    expect(importMarkup).toContain('aria-label="My Marginalia sections"');
    expect(importMarkup).toContain('type="file"');
  });

  it("requires a file locally and delegates a selected file to the SDK", async () => {
    const upload = vi.fn<(file: File) => Promise<ReadingImportPreview>>().mockResolvedValue(preview);
    await expect(previewSelectedMarginaliaImport(undefined, upload)).rejects.toBeInstanceOf(LocalValidationError);
    expect(upload).not.toHaveBeenCalled();
    const file = new File(["{}"], "marginalia.json", { type: "application/json" });
    await expect(previewSelectedMarginaliaImport(file, upload)).resolves.toBe(preview);
    expect(upload).toHaveBeenCalledWith(file);
  });

  it("renders a bounded upload and preview-before-apply explanation", () => {
    const markup = renderImport();
    expect(markup).toContain('type="file"');
    expect(markup).toContain('accept=".json,application/json"');
    expect(markup).toContain('type="submit"');
    expect(markup).not.toContain('type="checkbox"');
  });

  it("defaults every importable Session to selected and builds exact edits without mutating the draft", () => {
    const draft = createMarginaliaImportDraft(preview);
    expect(marginaliaImportSelectedCount(draft)).toBe(2);
    expect(draft[marginaliaImportSessionKey(1, 0)]?.selected).toBe(false);
    const edited = { ...draft, "0:0": { ...draft["0:0"]!, name: "Edited name", notes: "Edited notes" }, "0:1": { ...draft["0:1"]!, selected: false } };
    const before = structuredClone(edited);
    expect(buildMarginaliaImportApplyInput(preview, edited)).toEqual({ importToken: "opaque-token", books: [{ selectionReference: { source: "book:source", fileHash: "sha256:hidden", title: "Matched Book" }, sessions: [{ exportSessionId: "export-session-1", name: "Edited name", notes: "Edited notes" }] }] });
    expect(edited).toEqual(before);
  });

  it("supports all, none, and partial Book-level Session selection", () => {
    const all = createMarginaliaImportDraft(preview);
    expect(marginaliaImportBookSelectionState(preview, all, 0)).toBe("all");
    const none = withMarginaliaImportBookSelection(preview, all, 0, false);
    expect(marginaliaImportBookSelectionState(preview, none, 0)).toBe("none");
    expect(marginaliaImportSelectedCount(none)).toBe(0);
    const some = { ...none, "0:0": { ...none["0:0"]!, selected: true } };
    expect(marginaliaImportBookSelectionState(preview, some, 0)).toBe("some");
    expect(marginaliaImportSelectedCount(withMarginaliaImportBookSelection(preview, some, 0, true))).toBe(2);
    expect(marginaliaImportBookSelectionState(preview, all, 1)).toBe("none");
  });

  it("renders the matched Book selector checked or mixed and omits unmatched selectors", () => {
    const all = renderImport({ preview, draft: createMarginaliaImportDraft(preview) });
    expect(all.match(/type="checkbox"/g)).toHaveLength(3);
    const draft = createMarginaliaImportDraft(preview);
    draft["0:1"] = { ...draft["0:1"]!, selected: false };
    const partial = renderImport({ preview, draft });
    expect(partial).toContain('aria-checked="mixed"');
  });

  it("renders imported Book and note data without raw identifiers", () => {
    const markup = renderImport({ preview, draft: createMarginaliaImportDraft(preview) });
    expect(markup).toContain("Matched Book");
    expect(markup).toContain("Missing Book");
    expect(markup).toContain("Imported session");
    expect(markup).toContain("Remember this.");
    expect(markup).not.toContain("<textarea");
    expect(markup).toContain('role="tooltip"');
    expect(markup).not.toContain("export-session-");
    expect(markup).not.toContain("sha256:hidden");
  });

  it("reveals populated name and note controls only for the edited row", () => {
    const markup = renderImport({ preview, draft: createMarginaliaImportDraft(preview), editingSessionKeys: new Set(["0:0"]) });
    expect(markup).toContain("<textarea");
    expect(markup).toContain('value="Imported session"');
    expect(markup).toContain("Remember this.");
  });

  it("disables Apply when no Sessions are selected and keeps structured paths out of primary error prose", () => {
    const draft = createMarginaliaImportDraft(preview);
    Object.values(draft).forEach((session) => { session.selected = false; });
    const markup = renderImport({ preview, draft, previewError: new LocalValidationError("The archive could not be previewed.", { "books[0].sessions[0]": ["target is required"] }) });
    expect(markup).toContain('disabled=""');
    expect(markup).toContain("The archive could not be previewed");
    expect(markup).not.toContain("books[0].sessions[0]");
  });

  it("renders the apply result and returns to the Session list", () => {
    const result: ReadingImportResult = { applied: true, summary: { booksMatched: 1, booksSkipped: 0, sessionsCreated: 2, annotationsCreated: 5, bookmarksCreated: 2, highlightsCreated: 3, commentedHighlightsCreated: 1 }, warnings: [] };
    const markup = renderImport({ preview, draft: createMarginaliaImportDraft(preview), result });
    expect(markup).toContain('href="/marginalia"');
    expect(markup).not.toContain('type="checkbox"');
  });

  it("uses the canonical child breadcrumb trail", () => {
    expect(marginaliaImportBreadcrumbFallback).toEqual([
      { label: "My Marginalia", to: "/marginalia", resetTrail: true },
      { label: "Import", icon: "import" },
    ]);
  });
});
