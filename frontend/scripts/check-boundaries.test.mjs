import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, rmSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import { inspectSource, missingSourceRoots } from "./check-boundaries.mjs";

const workspace = fileURLToPath(new URL("..", import.meta.url));
const source = join(workspace, "src");

assertViolation(
  join(source, "features", "groups", "components", "GroupRowComponent.tsx"),
  'import { libraryThing } from "../../library/libraryThing";',
  "production feature-to-feature import",
);
assertViolation(
  join(source, "features", "groups", "regions", "GroupBooksPageRegion.tsx"),
  'import { listGroupBooks } from "@second-pass/spl-api";',
  "SDK operation import in presentational file",
);
assertNoViolation(
  join(source, "features", "groups", "regions", "GroupBooksPageRegion.tsx"),
  'import type { CompactBook } from "@second-pass/spl-api";',
);
assertViolation(
  join(source, "features", "groups", "components", "GroupRowComponent.tsx"),
  'import * as api from "@second-pass/spl-api";',
  "SDK operation import in presentational file",
);
assertViolation(
  join(source, "features", "shelves", "regions", "ShelfDetailsEditPageRegion.tsx"),
  'const message = error.fields?.sort_name;',
  "wire field name in React field error lookup",
);
assertViolation(
  join(source, "features", "shelves", "components", "ShelfRowComponent.tsx"),
  'const parameters = new URLSearchParams();',
  "query construction in presentational file",
);

const tempDir = mkdtempSync(join(source, ".check-boundaries-"));
try {
  const nestedTestsFile = createTempFile(tempDir, "features/foo/__tests__/example.ts", "export const value = 1;\n");
  assertNoViolation(nestedTestsFile, "export const value = 1;\n");

  const sharedFixtureDir = join(source, "shared", ".check-boundaries-shared-fixture");
  mkdirSync(sharedFixtureDir, { recursive: true });
  const sharedFile = createTempFile(sharedFixtureDir, "example.ts", 'export const value = fetch("/api/v1/thing");\n');
  const sharedViolations = inspectSource(sharedFile, 'export const value = fetch("/api/v1/thing");\n');
  assert.ok(sharedViolations.some((violation) => violation.includes("raw fetch in shared code")));
  assert.equal(sharedViolations.filter((violation) => violation.includes("raw fetch")).length, 1);

  const typeOnlyFile = createTempFile(tempDir, "components/ExampleComponent.tsx", 'import { type Thing } from "@second-pass/spl-api";\nexport const value = 1;\n');
  assertNoViolation(typeOnlyFile, 'import { type Thing } from "@second-pass/spl-api";\nexport const value = 1;\n');

  const reExportFile = createTempFile(tempDir, "components/ExampleComponent.tsx", 'export { createThing } from "@second-pass/spl-api";\n');
  assertViolation(reExportFile, 'export { createThing } from "@second-pass/spl-api";\n', "SDK operation import in presentational file");

  const typeReExportFile = createTempFile(tempDir, "components/TypeComponent.tsx", 'export { type Thing } from "@second-pass/spl-api";\n');
  assertNoViolation(typeReExportFile, 'export { type Thing } from "@second-pass/spl-api";\n');

  const declarationFile = createTempFile(tempDir, "features/foo/types.d.mts", 'export const path: "/api/v1/private";\n');
  assertNoViolation(declarationFile, 'export const path: "/api/v1/private";\n');

  const locatedImportFile = createTempFile(tempDir, "components/LocatedComponent.tsx", '\n\nimport { createThing } from "@second-pass/spl-api";\n');
  const locatedViolations = inspectSource(locatedImportFile, '\n\nimport { createThing } from "@second-pass/spl-api";\n');
  assert.ok(locatedViolations.some((violation) => violation.includes(":3:1 — SDK operation import in presentational file")));

  assert.deepEqual(missingSourceRoots([tempDir, join(tempDir, "missing")]), [join(tempDir, "missing")]);
} finally {
  rmSync(tempDir, { recursive: true, force: true });
  rmSync(join(source, "shared", ".check-boundaries-shared-fixture"), { recursive: true, force: true });
}

console.log("React boundary checker rules: OK");

function createTempFile(rootDir, relativePath, content) {
  const filePath = join(rootDir, relativePath);
  mkdirSync(dirname(filePath), { recursive: true });
  writeFileSync(filePath, content, "utf8");
  return filePath;
}

function assertViolation(file, content, expected) {
  const violations = inspectSource(file, content);
  assert.ok(violations.some((violation) => violation.endsWith(expected)), `Expected ${expected}; got ${violations.join(", ") || "none"}`);
}

function assertNoViolation(file, content) {
  assert.deepEqual(inspectSource(file, content), []);
}
