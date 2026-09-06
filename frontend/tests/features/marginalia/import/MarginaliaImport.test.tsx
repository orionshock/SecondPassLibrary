import { type CurrentUser, type MarginaliaImportApplyResult, type MarginaliaImportPreview, type ServerInfo } from "@second-pass/spl-api";
import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { AppOrchestrator } from "../../../../src/app/layout/AppOrchestrator";
import { MarginaliaImportOrchestrator, MarginaliaImportRequestGuard, previewSelectedMarginaliaImport } from "../../../../src/features/marginalia/import/MarginaliaImportOrchestrator";
import { MarginaliaSessionsOrchestrator } from "../../../../src/features/marginalia/browse/MarginaliaSessionsOrchestrator";
import { marginaliaImportBreadcrumbFallback } from "../../../../src/features/marginalia/marginaliaBreadcrumbs";
import {
  buildMarginaliaImportApplyInput,
  createMarginaliaImportDraft,
  marginaliaImportBookSelectionState,
  marginaliaImportSelectedCount,
  withMarginaliaImportBookSelection,
} from "../../../../src/features/marginalia/import/marginaliaImportDraft";
import { MarginaliaImportPageRegion } from "../../../../src/features/marginalia/import/MarginaliaImportPageRegion";
import { LocalValidationError } from "../../../../src/shared/feedback/mutationState";

const preview: MarginaliaImportPreview = {
  importToken: "opaque-token",
  includeEmptySessions: false,
  canApply: true,
  summary: { bookCount: 2, readingSessionCount: 3, annotationCount: 5 },
  matchedBookCount: 1,
  unmatchedBookCount: 1,
  unmatchedReadingSessionCount: 1,
  unmatchedDownloadableReadingSessionCount: 1,
  warnings: [{ code: "POSSIBLE_DUPLICATE_SESSION", message: "A similar Reading Session already exists.", candidateId: "reading-session-000002" }],
  books: [
    {
      candidateId: "book-000001",
      fileHash: "sha256:hidden",
      title: "Matched Book",
      authors: ["Author One"],
      match: { status: "matched", bookId: "local-book" },
      readingSessions: [
        {
          candidateId: "reading-session-000001",
          sourceReadingSessionId: "source-session-1",
          name: "Imported session",
          notes: "Remember this.",
          sourceStatus: "active",
          willImportAsStatus: "closed",
          startedAt: "2026-01-01T00:00:00Z",
          closedAt: null,
          annotationCount: 3,
          willImport: true,
          possibleDuplicate: false,
          warnings: [],
        },
        {
          candidateId: "reading-session-000002",
          sourceReadingSessionId: "source-session-2",
          name: "",
          notes: "",
          sourceStatus: "closed",
          willImportAsStatus: "closed",
          startedAt: "2026-01-02T00:00:00Z",
          closedAt: "2026-01-03T00:00:00Z",
          annotationCount: 2,
          willImport: true,
          possibleDuplicate: true,
          warnings: [{ code: "POSSIBLE_DUPLICATE_SESSION", message: "A similar Reading Session already exists.", candidateId: "reading-session-000002" }],
        },
      ],
    },
    {
      candidateId: "book-000002",
      fileHash: "sha256:missing",
      title: "Missing Book",
      authors: [],
      match: { status: "unmatched", reason: "book_inaccessible" },
      readingSessions: [{
        candidateId: "reading-session-000003",
        sourceReadingSessionId: "source-session-3",
        name: "Unavailable",
        notes: "",
        sourceStatus: "closed",
        willImportAsStatus: "closed",
        startedAt: "2026-01-04T00:00:00Z",
        closedAt: "2026-01-05T00:00:00Z",
        annotationCount: 0,
        willImport: false,
        possibleDuplicate: false,
        warnings: [],
      }],
    },
  ],
};

const user: CurrentUser = { username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader", mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderImport(options: {
  preview?: MarginaliaImportPreview;
  result?: MarginaliaImportApplyResult;
  draft?: ReturnType<typeof createMarginaliaImportDraft>;
  previewError?: Error;
  applyState?: { pending: boolean; error?: Error; message?: string };
  downloadState?: { pending: boolean; error?: Error; message?: string };
  editingSessionKeys?: ReadonlySet<string>;
} = {}) {
  return renderToStaticMarkup(<MemoryRouter><MarginaliaImportPageRegion
    preview={options.preview}
    result={options.result}
    draft={options.draft ?? {}}
    editingSessionKeys={options.editingSessionKeys ?? new Set()}
    previewState={{ pending: false, error: options.previewError }}
    applyState={options.applyState ?? { pending: false }}
    downloadState={options.downloadState ?? { pending: false }}
    inputRef={{ current: null }}
    includeEmptySessions={false}
    onIncludeEmptySessionsChange={vi.fn()}
    onFileChange={vi.fn()}
    onPreview={vi.fn()}
    onDraftChange={vi.fn()}
    onBookSelectionChange={vi.fn()}
    onEditingChange={vi.fn()}
    onDownloadUnmatched={vi.fn()}
    onApply={vi.fn()}
  /></MemoryRouter>);
}

describe("My Marginalia Import", () => {
  it("keeps the canonical Import route and preview upload controls", () => {
    const listMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/marginalia"]}><Routes><Route element={<AppOrchestrator user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="marginalia" element={<MarginaliaSessionsOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(listMarkup).toContain('href="/marginalia/import"');
    const importMarkup = renderToStaticMarkup(<MemoryRouter initialEntries={["/marginalia/import"]}><Routes><Route element={<AppOrchestrator user={user} server={server} onCurrentUserChange={vi.fn()} />}><Route path="marginalia/import" element={<MarginaliaImportOrchestrator />} /></Route></Routes></MemoryRouter>);
    expect(importMarkup).toContain('type="file"');
    expect(importMarkup).toContain("Include empty sessions");
  });

  it("requires a file locally and sends the staged empty-Session policy", async () => {
    const upload = vi.fn<(file: File, options: { includeEmptySessions?: boolean }) => Promise<MarginaliaImportPreview>>().mockResolvedValue(preview);
    await expect(previewSelectedMarginaliaImport(undefined, false, upload)).rejects.toBeInstanceOf(LocalValidationError);
    const file = new File(["{}"], "marginalia.json", { type: "application/json" });
    await expect(previewSelectedMarginaliaImport(file, true, upload)).resolves.toBe(preview);
    expect(upload).toHaveBeenCalledWith(file, { includeEmptySessions: true });
  });

  it("rejects a stale Preview result after file or policy invalidation", () => {
    const guard = new MarginaliaImportRequestGuard();
    const requestVersion = guard.begin();
    guard.invalidate();
    expect(guard.accepts(requestVersion)).toBe(false);
    expect(guard.accepts(guard.current())).toBe(true);
  });

  it("keys selection by candidate identity and never selects unmatched candidates", () => {
    const draft = createMarginaliaImportDraft(preview);
    expect(marginaliaImportSelectedCount(draft)).toBe(2);
    expect(draft["reading-session-000003"]?.selected).toBe(false);
    expect(marginaliaImportBookSelectionState(preview, draft, "book-000001")).toBe("all");
    const none = withMarginaliaImportBookSelection(preview, draft, "book-000001", false);
    expect(marginaliaImportBookSelectionState(preview, none, "book-000001")).toBe("none");
    expect(marginaliaImportBookSelectionState(preview, draft, "book-000002")).toBe("none");
  });

  it("submits only selected candidate IDs and changed overrides", () => {
    const draft = createMarginaliaImportDraft(preview);
    const edited = {
      ...draft,
      "reading-session-000001": { ...draft["reading-session-000001"]!, name: "Edited name", notes: "Edited notes" },
      "reading-session-000002": { ...draft["reading-session-000002"]!, selected: false },
    };
    expect(buildMarginaliaImportApplyInput(preview, edited)).toEqual({
      importToken: "opaque-token",
      readingSessions: [{ candidateId: "reading-session-000001", name: "Edited name", notes: "Edited notes" }],
    });
  });

  it("renders staged match and duplicate state without exposing import identities", () => {
    const markup = renderImport({ preview, draft: createMarginaliaImportDraft(preview) });
    expect(markup).toContain("Matched Book");
    expect(markup).toContain("Missing Book");
    expect(markup).toContain("Possible Duplicate Session");
    expect(markup).not.toContain("sha256:hidden");
    expect(markup).not.toContain("source-session-1");
  });

  it("gives an unmatched checksum a safe, actionable recovery path", () => {
    const unmatchedPreview = {
      ...preview,
      books: preview.books.map((book) => book.candidateId === "book-000002"
        ? { ...book, match: { status: "unmatched" as const, reason: "not_found" as const } }
        : book),
    };

    const markup = renderImport({
      preview: unmatchedPreview,
      draft: createMarginaliaImportDraft(unmatchedPreview),
    });

    expect(markup).toContain("exact EPUB file checksum");
    expect(markup).toContain("Import the same EPUB file");
    expect(markup).not.toContain("sha256:missing");
  });

  it("keeps candidate-driven Book bulk selection and optional Session editors", () => {
    const draft = createMarginaliaImportDraft(preview);
    draft["reading-session-000002"] = { ...draft["reading-session-000002"]!, selected: false };
    const markup = renderImport({ preview, draft, editingSessionKeys: new Set(["reading-session-000001"]) });
    expect(markup).toContain('aria-label="Select all importable sessions from Matched Book"');
    expect(markup).not.toContain('aria-label="Select all importable sessions from Missing Book"');
    expect(markup).toContain('aria-checked="mixed"');
    expect(markup).toContain("<textarea");
    expect(markup).toContain('value="Imported session"');
  });

  it("shows unmatched download only for the staged downloadable count", () => {
    const markup = renderImport({ preview, draft: createMarginaliaImportDraft(preview) });
    expect(markup).toContain("Download Unmatched Sessions (1)");
    const empty = { ...preview, unmatchedDownloadableReadingSessionCount: 0 };
    expect(renderImport({ preview: empty, draft: createMarginaliaImportDraft(empty) })).not.toContain("Download Unmatched Sessions");
  });

  it("keeps Apply and unmatched feedback independent while preserving review content", () => {
    const markup = renderImport({
      preview,
      draft: createMarginaliaImportDraft(preview),
      applyState: { pending: false, error: new Error("Apply needs attention.") },
      downloadState: { pending: false, error: new Error("ZIP download failed.") },
    });
    expect(markup).toContain("Apply needs attention.");
    expect(markup).toContain("ZIP download failed.");
    expect(markup).toContain("Imported session");
    expect(markup).toContain("Import Selected Sessions");
  });

  it("disables Apply for an empty selection", () => {
    const draft = createMarginaliaImportDraft(preview);
    Object.values(draft).forEach((session) => { session.selected = false; });
    const markup = renderImport({ preview, draft });
    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>Import Selected Sessions<\/button>/);
  });

  it("renders canonical imported counts and candidate-to-created Session results", () => {
    const result: MarginaliaImportApplyResult = {
      importedReadingSessionCount: 1,
      importedAnnotationCount: 3,
      unmatchedReadingSessionCount: 1,
      unmatchedDownloadableReadingSessionCount: 1,
      unmatchedDownloadAvailable: true,
      unmatchedBooks: [{ candidateId: "book-000002", title: "Missing Book", reason: "book_inaccessible" }],
      readingSessions: [{ candidateId: "reading-session-000001", readingSessionId: "local-session", status: "closed", name: "Imported session", annotationCount: 3 }],
      warnings: [],
    };
    const markup = renderImport({ preview, draft: createMarginaliaImportDraft(preview), result });
    expect(markup).toContain("1 session created");
    expect(markup).toContain("3 annotations created");
    expect(markup).toContain('href="/marginalia/sessions/local-session"');
    expect(markup).toContain("1 Session remains unmatched");
    expect(markup).toContain("Download Unmatched Sessions (1)");
    expect(markup).toContain("Missing Book");
    expect(markup).not.toContain("Something went wrong");
    expect(markup).toContain("Closed");
    expect(markup).not.toContain("Select all importable sessions");
  });

  it("uses the canonical child breadcrumb trail", () => {
    expect(marginaliaImportBreadcrumbFallback).toEqual([
      { label: "My Marginalia", to: "/marginalia", resetTrail: true },
      { label: "Import", icon: "import" },
    ]);
  });
});
