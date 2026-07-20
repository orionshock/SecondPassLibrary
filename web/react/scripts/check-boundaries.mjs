import { readFileSync, readdirSync } from "node:fs";
import { extname, join, relative } from "node:path";
import { fileURLToPath } from "node:url";

const workspace = fileURLToPath(new URL("..", import.meta.url));
const appSource = join(workspace, "src");
const sharedComponents = join(appSource, "components");
const sdkSource = join(workspace, "packages", "spl-api", "src");
const sourceExtensions = new Set([".ts", ".tsx"]);

const violations = [];

scan(appSource, (file, source) => {
  if (isSdkTest(file)) return;
  check(file, source, /\bfetch\s*\(/, "raw fetch");
  check(file, source, /\/api\/v1(?:\/|\b)/, "raw API path");
  check(file, source, /\/\.well-known(?:\/|\b)/, "raw well-known path");
  check(file, source, /csrftoken|X-CSRFToken/i, "CSRF implementation detail");
});

scan(sharedComponents, (file, source) => {
  check(file, source, /@second-pass\/spl-api/, "SDK import in a shared UI primitive");
});

scan(sdkSource, (file, source) => {
  check(file, source, /from\s+["']react(?:\/|["'])/, "React import in the SDK");
});

if (violations.length > 0) {
  console.error(`React boundary check failed:\n${violations.join("\n")}`);
  process.exit(1);
}

console.log("React SDK/component boundaries: OK");

function scan(directory, inspect) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) scan(path, inspect);
    else if (sourceExtensions.has(extname(entry.name))) inspect(path, readFileSync(path, "utf8"));
  }
}

function check(file, source, pattern, label) {
  if (pattern.test(source)) {
    violations.push(`- ${relative(workspace, file)}: ${label}`);
  }
}

function isSdkTest(file) {
  const path = relative(appSource, file).replaceAll("\\", "/");
  return path.startsWith("__tests__/sdk.");
}
