import assert from "node:assert/strict";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

import { inspectSource } from "./check-boundaries.mjs";

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

console.log("React boundary checker rules: OK");

function assertViolation(file, content, expected) {
  const violations = inspectSource(file, content);
  assert.ok(violations.some((violation) => violation.endsWith(expected)), `Expected ${expected}; got ${violations.join(", ") || "none"}`);
}

function assertNoViolation(file, content) {
  assert.deepEqual(inspectSource(file, content), []);
}
