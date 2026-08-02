import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ApiError, canSeeImports, type CurrentUser, type LibraryImportResult, type ServerInfo } from "@second-pass/spl-api";
import { AppFrame } from "../app/layout/AppFrame";
import { readIncomingBreadcrumbTrail } from "../app/navigation/breadcrumbs";
import { clearImportFileInput, importResultBookNavigation, importsBreadcrumbFallback, ImportsOrchestrator, uploadSelectedLibraryFile } from "../features/imports/ImportsOrchestrator";
import { ImportResultPageRegion } from "../features/imports/regions/ImportResultPageRegion";
import { ImportUploadPageRegion } from "../features/imports/regions/ImportUploadPageRegion";
import { LocalValidationError } from "../shared/feedback/mutationState";

const owner: CurrentUser = {
  username: "owner", email: "", firstName: "", lastName: "", profileId: "owner", role: "manager",
  mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
};
const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, readingClientBaseUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

function renderRoute(user: CurrentUser) {
  return renderToStaticMarkup(<MemoryRouter initialEntries={["/imports"]}><Routes>
    <Route element={<AppFrame user={user} server={server} onCurrentUserChange={vi.fn()} />}>
      <Route path="imports" element={<ImportsOrchestrator />} />
    </Route>
  </Routes></MemoryRouter>);
}

describe("Imports", () => {
  it("allows Librarian, Manager, and Owner while rejecting Reader access", () => {
    expect(canSeeImports(owner)).toBe(true);
    expect(canSeeImports({ isOwner: false, isManager: true, isLibrarian: false, isReader: false })).toBe(true);
    expect(canSeeImports({ isOwner: false, isManager: false, isLibrarian: true, isReader: false })).toBe(true);
    expect(canSeeImports({ isOwner: false, isManager: false, isLibrarian: false, isReader: true })).toBe(false);
    expect(renderRoute(owner)).toContain('accept=".epub,.zip"');
    const denied = renderRoute({ ...owner, isOwner: false, isReader: true, role: "reader" });
    expect(denied).toContain('role="alert"');
    expect(denied).not.toContain('type="file"');
  });

  it("renders a native pending upload form with action feedback placement", () => {
    const markup = renderToStaticMarkup(<ImportUploadPageRegion state={{ pending: true }} inputRef={{ current: null }} onFileChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(markup).toContain('type="file"');
    expect(markup).toContain('accept=".epub,.zip"');
    expect(markup).toContain('disabled=""');
    expect(markup.indexOf("action-feedback")).toBeLessThan(markup.indexOf('type="submit"'));
  });

  it("blocks an empty selection before upload and clears the native input after success", async () => {
    const upload = vi.fn<(file: File) => Promise<LibraryImportResult>>();
    const missingFile = uploadSelectedLibraryFile(undefined, upload).catch((error: unknown) => error);
    await expect(missingFile).resolves.toBeInstanceOf(LocalValidationError);
    await expect(missingFile).resolves.not.toBeInstanceOf(ApiError);
    await expect(missingFile).resolves.toMatchObject({ fields: { file: expect.any(Array) } });
    expect(upload).not.toHaveBeenCalled();
    const input = { value: "C:\\fakepath\\book.epub" };
    clearImportFileInput(input);
    expect(input.value).toBe("");
    const errorMarkup = renderToStaticMarkup(<ImportUploadPageRegion
      state={{ pending: false, error: new LocalValidationError("Choose a file to import.", { file: ["Choose a file to import."] }) }}
      inputRef={{ current: null }} onFileChange={vi.fn()} onSubmit={vi.fn()}
    />);
    expect(errorMarkup).toContain('class="field-error"');
    expect(errorMarkup).toContain('role="alert"');
  });

  it("renders every returned item and links results with known Books", () => {
    const items = Array.from({ length: 55 }, (_, index) => ({
      status: index === 54 ? "failed" as const : "imported" as const,
      sourceLabel: `safe-${index}.epub`, safeMessage: index === 54 ? "Invalid EPUB package." : "", bookId: `uuid-${index}`,
      ...(index === 0 ? { title: "Human title", authors: ["First Author", "Second Author"], series: "Human series", seriesIndex: "1.00" } : {}),
    }));
    const result: LibraryImportResult = {
      sourceType: "zip", sourceLabel: "batch.zip",
      counts: { imported: 54, duplicate: 0, conflict: 0, failed: 1, skipped: 0 }, items,
    };
    const markup = renderToStaticMarkup(<MemoryRouter><ImportResultPageRegion
      result={result}
      bookNavigation={importResultBookNavigation}
    /></MemoryRouter>);
    expect(markup).toContain('href="/library/books/uuid-0"');
    expect((markup.match(/class="import-result-item /g) ?? [])).toHaveLength(55);
  });

  it("keeps results without a known Book non-interactive", () => {
    const result: LibraryImportResult = {
      sourceType: "epub", sourceLabel: "fallback.epub",
      counts: { imported: 1, duplicate: 0, conflict: 0, failed: 0, skipped: 0 },
      items: [{ status: "imported", sourceLabel: "fallback.epub", safeMessage: "Imported." }],
    };
    const markup = renderToStaticMarkup(<MemoryRouter><ImportResultPageRegion
      result={result}
      bookNavigation={importResultBookNavigation}
    /></MemoryRouter>);
    expect(markup).not.toContain("<a");
  });

  it("carries import breadcrumb context to Book Detail", () => {
    const navigation = importResultBookNavigation("book/id", "Imported Book");
    expect(navigation.to).toBe("/library/books/book%2Fid");
    expect(readIncomingBreadcrumbTrail(navigation.state)).toEqual([
      { label: "Book Import", to: "/imports", resetTrail: true, icon: "import" },
      { label: "Imported Book", icon: "book" },
    ]);
  });

  it("uses no breadcrumb on the base Imports route", () => {
    expect(importsBreadcrumbFallback).toEqual([]);
  });
});
