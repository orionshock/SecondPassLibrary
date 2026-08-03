import { readFileSync, readdirSync } from "node:fs";
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const workspace = fileURLToPath(new URL("..", import.meta.url));
const appSource = join(workspace, "src");
const featuresSource = join(appSource, "features");
const sharedComponents = join(appSource, "components");
const sharedSource = join(appSource, "shared");
const sdkSource = join(workspace, "packages", "spl-api", "src");
const sourceExtensions = new Set([".ts", ".tsx"]);

if (process.argv[1] === fileURLToPath(import.meta.url)) {
  const violations = [];

  scan(appSource, (file, source) => violations.push(...inspectSource(file, source)));
  scan(sdkSource, (file, source) => violations.push(...inspectSource(file, source)));

  if (violations.length > 0) {
    console.error(`React boundary check failed:\n${violations.join("\n")}`);
    process.exit(1);
  }

  console.log("React SDK/component boundaries: OK");
}

export function inspectSource(file, source) {
  if (isTestOrDeclaration(file)) return [];

  const labels = [];
  const imports = extractImports(source);

  if (isWithin(appSource, file)) {
    find(labels, source, /\bfetch\s*\(/, "raw fetch");
    find(labels, source, /\/api\/v1(?:\/|\b)/, "raw API path");
    find(labels, source, /\/\.well-known(?:\/|\b)/, "raw well-known path");
    find(labels, source, /csrftoken|X-CSRFToken/i, "CSRF implementation detail");
    find(labels, source, /fieldError\([^)]*,\s*["'][a-z]+_[a-z_]+["']\s*\)/, "wire field name in React field error lookup");
    find(labels, source, /fields\s*:\s*\{\s*[a-z]+_[a-z_]+\s*:/, "wire field name in React field error construction");
    find(labels, source, /\b(?:error\s*\.\s*fields|fieldErrors)\s*(?:\?\.|\.)\s*[a-z][a-z0-9]*_[a-z0-9_]+\b/i, "wire field name in React field error lookup");
    find(labels, source, /\b(?:error\s*\.\s*fields|fieldErrors)\s*(?:\?\.)?\s*\[\s*["'][a-z][a-z0-9]*_[a-z0-9_]+["']\s*\]/i, "wire field name in React field error lookup");

    if (isPresentationalFile(file)) {
      if (imports.some((entry) => isSdkSpecifier(entry.specifier) && !entry.typeOnly)) {
        labels.push("SDK operation import in presentational file");
      }
      find(labels, source, /\bnew\s+URLSearchParams\s*\(/, "query construction in presentational file");
    }

    if (isWithin(featuresSource, file)) {
      const sourceFeature = featureName(file);
      if (sourceFeature && imports.some((entry) => importedFeature(file, entry.specifier) !== null && importedFeature(file, entry.specifier) !== sourceFeature)) {
        labels.push("production feature-to-feature import");
      }
    }

    if (isWithin(sharedComponents, file)) {
      if (imports.some((entry) => isSdkSpecifier(entry.specifier))) labels.push("SDK import in a shared UI primitive");
    }

    if (isWithin(sharedSource, file)) {
      if (imports.some((entry) => isSdkSpecifier(entry.specifier))) labels.push("SDK import in shared code");
      find(labels, source, /\bfetch\s*\(/, "raw fetch in shared code");
      find(labels, source, /\/api\/v1(?:\/|\b)/, "raw API path in shared code");
    }
  }

  if (isWithin(sdkSource, file) && imports.some((entry) => isReactSpecifier(entry.specifier))) {
    labels.push("React import in the SDK");
  }

  return labels.map((label) => `- ${relative(workspace, file)}: ${label}`);
}

function scan(directory, inspect) {
  for (const entry of readdirSync(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) scan(path, inspect);
    else if (sourceExtensions.has(extname(entry.name))) inspect(path, readFileSync(path, "utf8"));
  }
}

function find(labels, source, pattern, label) {
  if (pattern.test(source)) labels.push(label);
}

function extractImports(source) {
  const imports = [];
  const fromPattern = /^\s*import\s+([^;"']+?)\s+from\s+["']([^"']+)["']/gm;
  const sideEffectPattern = /^\s*import\s+["']([^"']+)["']/gm;

  for (const match of source.matchAll(fromPattern)) {
    imports.push({ specifier: match[2], typeOnly: match[1].trim().startsWith("type ") });
  }
  for (const match of source.matchAll(sideEffectPattern)) {
    imports.push({ specifier: match[1], typeOnly: false });
  }
  return imports;
}

function isPresentationalFile(file) {
  return /(?:PageRegion|Component|SubComponent)\.tsx$/.test(file);
}

function isSdkSpecifier(specifier) {
  return specifier === "@second-pass/spl-api" || specifier.startsWith("@second-pass/spl-api/");
}

function isReactSpecifier(specifier) {
  return specifier === "react" || specifier.startsWith("react/") || specifier === "react-dom" || specifier.startsWith("react-dom/");
}

function featureName(file) {
  const path = relative(featuresSource, file);
  if (path.startsWith(`..${sep}`) || path === ".." || isAbsolute(path)) return null;
  return path.split(sep)[0] ?? null;
}

function importedFeature(file, specifier) {
  let target;
  if (specifier.startsWith(".")) target = resolve(dirname(file), specifier);
  else if (specifier.startsWith("features/")) target = join(appSource, specifier);
  else if (specifier.startsWith("@/features/")) target = join(appSource, specifier.slice(2));
  else return null;

  return featureName(target);
}

function isWithin(directory, file) {
  const path = relative(directory, file);
  return path === "" || (!path.startsWith(`..${sep}`) && path !== ".." && !isAbsolute(path));
}

function isTestOrDeclaration(file) {
  const path = relative(appSource, file).replaceAll("\\", "/");
  return path.startsWith("__tests__/") || /\.(?:test|spec)\.[jt]sx?$/.test(file) || file.endsWith(".d.ts");
}
