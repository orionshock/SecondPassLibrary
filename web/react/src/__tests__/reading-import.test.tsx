import type { CurrentUser, ReadingImportPreview, ReadingImportResult, ServerInfo } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { readingImportBreadcrumbFallback } from "../features/reading/readingBreadcrumbs";
import { ReadingImportOrchestrator, previewSelectedReadingImport } from "../features/reading/ReadingImportOrchestrator";
import { ReadingSessionsOrchestrator } from "../features/reading/ReadingSessionsOrchestrator";
import { AppFrame } from "../app/layout/AppFrame";
import { buildReadingImportApplyInput, createReadingImportDraft, readingImportBookSelectionState, readingImportSelectedCount, readingImportSessionKey, withReadingImportBookSelection } from "../features/reading/readingImportDraft";
import { ReadingImportPageRegion } from "../features/reading/regions/ReadingImportPageRegion";
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
const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderImport(options: { preview?: ReadingImportPreview; result?: ReadingImportResult; draft?: ReturnType<typeof createReadingImportDraft>; previewError?: Error; editingSessionKeys?: ReadonlySet<string> } = {}) {
  return renderToStaticMarkup(<MemoryRouter><ReadingImportPageRegion
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
    const listMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/reading"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="reading" element={<ReadingSessionsOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(listMarkup).toContain('href="/reading/import"');
    expect(listMarkup).toContain("Import");
    const importMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/reading/import"]}><Routes><Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="reading/import" element={<ReadingImportOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(importMarkup).toContain("My Marginalia");
    expect(importMarkup).toContain("Marginalia archive");
  });

  it("requires a file locally and delegates a selected file to the SDK", async () => {
    const upload = vi.fn<(file: File) => Promise<ReadingImportPreview>>().mockResolvedValue(preview);
    await expect(previewSelectedReadingImport(undefined, upload)).rejects.toBeInstanceOf(LocalValidationError);
    expect(upload).not.toHaveBeenCalled();
    const file = new File(["{}"], "marginalia.json", { type: "application/json" });
    await expect(previewSelectedReadingImport(file, upload)).resolves.toBe(preview);
    expect(upload).toHaveBeenCalledWith(file);
  });

  it("renders a bounded upload and preview-before-apply explanation", () => {
    const markup = renderImport();
    expect(markup).toContain('type="file"');
    expect(markup).toContain('accept=".json,application/json"');
    expect(markup).toContain("Nothing changes until");
    expect(markup).toContain("Preview");
    expect(markup).not.toContain("Apply selected");
  });

  it("defaults every importable Session to selected and builds exact edits without mutating the draft", () => {
    const draft = createReadingImportDraft(preview);
    expect(readingImportSelectedCount(draft)).toBe(2);
    expect(draft[readingImportSessionKey(1, 0)]?.selected).toBe(false);
    const edited = { ...draft, "0:0": { ...draft["0:0"]!, name: "Edited name", notes: "Edited notes" }, "0:1": { ...draft["0:1"]!, selected: false } };
    const before = structuredClone(edited);
    expect(buildReadingImportApplyInput(preview, edited)).toEqual({ importToken: "opaque-token", books: [{ selectionReference: { source: "book:source", fileHash: "sha256:hidden", title: "Matched Book" }, sessions: [{ exportSessionId: "export-session-1", name: "Edited name", notes: "Edited notes" }] }] });
    expect(edited).toEqual(before);
  });

  it("supports all, none, and partial Book-level Session selection", () => {
    const all = createReadingImportDraft(preview);
    expect(readingImportBookSelectionState(preview, all, 0)).toBe("all");
    const none = withReadingImportBookSelection(preview, all, 0, false);
    expect(readingImportBookSelectionState(preview, none, 0)).toBe("none");
    expect(readingImportSelectedCount(none)).toBe(0);
    const some = { ...none, "0:0": { ...none["0:0"]!, selected: true } };
    expect(readingImportBookSelectionState(preview, some, 0)).toBe("some");
    expect(readingImportSelectedCount(withReadingImportBookSelection(preview, some, 0, true))).toBe(2);
    expect(readingImportBookSelectionState(preview, all, 1)).toBe("none");
  });

  it("renders the matched Book selector checked or mixed and omits unmatched selectors", () => {
    const all = renderImport({ preview, draft: createReadingImportDraft(preview) });
    expect(all).toContain('aria-label="Select all importable sessions from Matched Book"');
    expect(all).not.toContain('aria-label="Select all importable sessions from Missing Book"');
    expect(all.match(/type="checkbox"/g)).toHaveLength(3);
    const draft = createReadingImportDraft(preview);
    draft["0:1"] = { ...draft["0:1"]!, selected: false };
    const partial = renderImport({ preview, draft });
    expect(partial).toContain('aria-checked="mixed"');
  });

  it("renders compact matched, unmatched, selectable, warning, and note-preview states without raw identifiers", () => {
    const markup = renderImport({ preview, draft: createReadingImportDraft(preview) });
    expect(markup).toContain("Matched Book");
    expect(markup).toContain("Missing Book");
    expect(markup).toContain("Matched");
    expect(markup).toContain("Unmatched");
    expect(markup).toContain("Imported session");
    expect(markup).toContain("Unnamed session");
    expect(markup).toContain("2 sessions selected");
    expect(markup).toContain("Remember this.");
    expect(markup).toContain("3 annotations");
    expect(markup).toContain("Imports as historical");
    expect(markup).toContain(">Edit</button>");
    expect(markup).not.toContain("Imported name");
    expect(markup).not.toContain("Imported note");
    expect(markup).toContain('aria-label="Why Missing Book is unmatched"');
    expect(markup).toContain('role="tooltip"');
    expect(markup.match(/No visible local book matched this export book\./g)).toHaveLength(1);
    expect(markup).not.toContain("export-session-");
    expect(markup).not.toContain("sha256:hidden");
  });

  it("reveals singular imported name and note controls only for the edited row", () => {
    const markup = renderImport({ preview, draft: createReadingImportDraft(preview), editingSessionKeys: new Set(["0:0"]) });
    expect(markup).toContain("Imported name");
    expect(markup).toContain("Imported note");
    expect(markup).not.toContain("Imported notes");
    expect(markup).toContain(">Done</button>");
    expect(markup).toContain('value="Imported session"');
    expect(markup).toContain("Remember this.");
  });

  it("disables Apply when no Sessions are selected and keeps structured paths out of primary error prose", () => {
    const draft = createReadingImportDraft(preview);
    Object.values(draft).forEach((session) => { session.selected = false; });
    const markup = renderImport({ preview, draft, previewError: new LocalValidationError("The archive could not be previewed.", { "books[0].sessions[0]": ["target is required"] }) });
    expect(markup).toContain('disabled=""');
    expect(markup).toContain("0 sessions selected");
    expect(markup).toContain("The archive could not be previewed");
    expect(markup).not.toContain("books[0].sessions[0]");
  });

  it("renders the apply result and returns to the Session list", () => {
    const result: ReadingImportResult = { applied: true, summary: { booksMatched: 1, booksSkipped: 0, sessionsCreated: 2, annotationsCreated: 5, bookmarksCreated: 2, highlightsCreated: 3, commentedHighlightsCreated: 1 }, warnings: [] };
    const markup = renderImport({ preview, draft: createReadingImportDraft(preview), result });
    expect(markup).toContain("Import complete");
    expect(markup).toContain("2 sessions created");
    expect(markup).toContain('href="/reading"');
    expect(markup).not.toContain("Apply selected");
  });

  it("uses the canonical child breadcrumb trail", () => {
    expect(readingImportBreadcrumbFallback).toEqual([
      { label: "My Marginalia", to: "/reading", resetTrail: true },
      { label: "Import", icon: "import" },
    ]);
  });
});
