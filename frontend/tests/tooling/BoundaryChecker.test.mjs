import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

import {
  inspectSource,
  isPresentationalFile,
  missingSourceRoots,
} from "../../scripts/check-boundaries.mjs";

const frontendRoot = resolve(import.meta.dirname, "../..");
const appSource = resolve(frontendRoot, "src");
const sdkSource = resolve(frontendRoot, "packages/spl-api/src");

function appFile(relativePath) {
  return resolve(appSource, relativePath);
}

function labels(file, source) {
  return inspectSource(file, source);
}

describe("React source boundary checker", () => {
  it("distinguishes type-only SDK imports from runtime imports in presentational files", () => {
    const file = appFile("features/library/BookPageRegion.tsx");

    expect(labels(file, 'import type { Book } from "@second-pass/spl-api";')).toEqual([]);
    expect(labels(file, 'export type { Book } from "@second-pass/spl-api";')).toEqual([]);
    expect(labels(file, 'import { listBooks } from "@second-pass/spl-api";'))
      .toEqual([expect.stringContaining("SDK operation import in presentational file")]);
  });

  it("rejects raw transport and CSRF details in Product UI source", () => {
    const file = appFile("features/library/LibraryOrchestrator.tsx");
    const violations = labels(file, `
      fetch("/api/v1/books");
      const token = "csrftoken";
      const discovery = "/.well-known/second-pass";
    `);

    expect(violations).toContainEqual(expect.stringContaining("raw fetch"));
    expect(violations).toContainEqual(expect.stringContaining("raw API path"));
    expect(violations).toContainEqual(expect.stringContaining("CSRF implementation detail"));
    expect(violations).toContainEqual(expect.stringContaining("raw well-known path"));
  });

  it("rejects feature-to-feature production imports but ignores local structure", () => {
    const file = appFile("features/library/LibraryOrchestrator.tsx");

    expect(labels(file, 'import { groupState } from "../groups/groupState";'))
      .toContainEqual(expect.stringContaining("production feature-to-feature import"));
    expect(labels(file, 'import { libraryState } from "./libraryState";')).toEqual([]);
  });

  it("enforces presentational and shared-layer restrictions", () => {
    const presentational = appFile("features/library/BookPageRegion.tsx");
    const shared = appFile("shared/books/bookPresentation.ts");

    expect(labels(presentational, "const query = new URLSearchParams();"))
      .toContainEqual(expect.stringContaining("query construction in presentational file"));
    expect(labels(shared, 'import { listBooks } from "@second-pass/spl-api"; fetch("/api/v1/books");'))
      .toEqual(expect.arrayContaining([
        expect.stringContaining("SDK import in shared code"),
        expect.stringContaining("raw fetch in shared code"),
        expect.stringContaining("raw API path in shared code"),
      ]));
  });

  it("keeps React out of the SDK and recognizes presentational role paths", () => {
    const sdkFile = resolve(sdkSource, "library.ts");

    expect(labels(sdkFile, 'import type { ReactNode } from "react";'))
      .toContainEqual(expect.stringContaining("React import in the SDK"));
    expect(isPresentationalFile(appFile("features/library/BookPageRegion.tsx"))).toBe(true);
    expect(isPresentationalFile(appFile("features/library/libraryQuery.ts"))).toBe(false);
  });

  it("ignores test/declaration sources and reports missing scan roots", () => {
    expect(labels(
      appFile("features/library/LibraryOrchestrator.test.tsx"),
      'fetch("/api/v1/books");',
    )).toEqual([]);
    expect(labels(
      appFile("features/library/libraryTypes.d.ts"),
      'import { listBooks } from "@second-pass/spl-api";',
    )).toEqual([]);

    const missing = resolve(frontendRoot, "definitely-missing-source-root");
    expect(missingSourceRoots([appSource, missing])).toEqual([missing]);
  });
});
