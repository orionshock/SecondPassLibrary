import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, extname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";

const workspace = fileURLToPath(new URL("..", import.meta.url));
const appSource = join(workspace, "src");
const featuresSource = join(appSource, "features");
const sharedComponents = join(appSource, "components");
const sharedSource = join(appSource, "shared");
const sdkSource = join(workspace, "packages", "spl-api", "src");
const sourceExtensions = new Set([".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"]);

const scriptPath = resolve(fileURLToPath(import.meta.url));
const invokedPath = process.argv[1] ? resolve(process.argv[1]) : null;

if (invokedPath && invokedPath === scriptPath) {
  const violations = [];
  const missingRoots = missingSourceRoots([appSource, sdkSource]);

  if (missingRoots.length > 0) {
    console.error(`React boundary check failed: required source root missing:\n${missingRoots.map((root) => `- ${relative(workspace, root)}`).join("\n")}`);
    process.exit(1);
  }

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

  const violations = [];
  const imports = extractImports(source);
  const withinShared = isWithin(sharedSource, file);

  if (isWithin(appSource, file)) {
    if (!withinShared) {
      find(violations, source, /\bfetch\s*\(/, "raw fetch");
      find(violations, source, /\/api\/v1(?:\/|\b)/, "raw API path");
    }
    find(violations, source, /\/\.well-known(?:\/|\b)/, "raw well-known path");
    find(violations, source, /csrftoken|X-CSRFToken/i, "CSRF implementation detail");
    find(violations, source, /fieldError\([^)]*,\s*["'][a-z]+_[a-z_]+["']\s*\)/, "wire field name in React field error lookup");
    find(violations, source, /fields\s*:\s*\{\s*[a-z]+_[a-z_]+\s*:/, "wire field name in React field error construction");
    find(violations, source, /\b(?:error\s*\.\s*fields|fieldErrors)\s*(?:\?\.|\.)\s*[a-z][a-z0-9]*_[a-z0-9_]+\b/i, "wire field name in React field error lookup");
    find(violations, source, /\b(?:error\s*\.\s*fields|fieldErrors)\s*(?:\?\.)?\s*\[\s*["'][a-z][a-z0-9]*_[a-z0-9_]+["']\s*\]/i, "wire field name in React field error lookup");

    if (isPresentationalFile(file)) {
      const sdkOperation = imports.find((entry) => isSdkSpecifier(entry.specifier) && !entry.typeOnly);
      if (sdkOperation) {
        violations.push(makeViolation("SDK operation import in presentational file", source, sdkOperation.index));
      }
      find(violations, source, /\bnew\s+URLSearchParams\s*\(/, "query construction in presentational file");
    }

    if (isWithin(featuresSource, file)) {
      const sourceFeature = featureName(file);
      const foreignFeatureImport = sourceFeature
        ? imports.find((entry) => {
          const targetFeature = importedFeature(file, entry.specifier);
          return targetFeature !== null && targetFeature !== sourceFeature;
        })
        : undefined;
      if (foreignFeatureImport) {
        violations.push(makeViolation("production feature-to-feature import", source, foreignFeatureImport.index));
      }
    }

    if (isWithin(sharedComponents, file)) {
      const sdkImport = imports.find((entry) => isSdkSpecifier(entry.specifier));
      if (sdkImport) violations.push(makeViolation("SDK import in a shared UI primitive", source, sdkImport.index));
    }

    if (withinShared) {
      const sdkImport = imports.find((entry) => isSdkSpecifier(entry.specifier));
      if (sdkImport) violations.push(makeViolation("SDK import in shared code", source, sdkImport.index));
      find(violations, source, /\bfetch\s*\(/, "raw fetch in shared code");
      find(violations, source, /\/api\/v1(?:\/|\b)/, "raw API path in shared code");
    }
  }

  const reactImport = imports.find((entry) => isReactSpecifier(entry.specifier));
  if (isWithin(sdkSource, file) && reactImport) {
    violations.push(makeViolation("React import in the SDK", source, reactImport.index));
  }

  return violations.map((violation) => `- ${relative(workspace, file)}:${violation.line}:${violation.column} — ${violation.label}`);
}

function scan(directory, inspect) {
  for (const entry of readdirSync(directory, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) scan(path, inspect);
    else if (sourceExtensions.has(extname(entry.name))) inspect(path, readFileSync(path, "utf8"));
  }
}

function find(labels, source, pattern, label) {
  const match = source.match(pattern);
  if (!match) return;

  const index = source.indexOf(match[0]);
  labels.push(makeViolation(label, source, index));
}

function makeViolation(label, source, index = 0) {
  const { line, column } = locate(source, index);
  return { label, line, column };
}

function locate(source, index) {
  let line = 1;
  let column = 1;

  for (let offset = 0; offset < index; offset += 1) {
    if (source[offset] === "\n") {
      line += 1;
      column = 1;
    } else {
      column += 1;
    }
  }

  return { line, column };
}

function extractImports(source) {
  const imports = [];
  const fromPattern = /^\s*import\s+([^;"']+?)\s+from\s+["']([^"']+)["']/gm;
  const sideEffectPattern = /^\s*import\s+["']([^"']+)["']/gm;
  const exportFromPattern = /^\s*export\s+(type\s+)?(\*|[^;]+?)\s+from\s+["']([^"']+)["']/gm;

  for (const match of source.matchAll(fromPattern)) {
    imports.push({ specifier: match[2], typeOnly: isTypeOnlyImportClause(match[1].trim()), index: statementIndex(match, "import") });
  }
  for (const match of source.matchAll(sideEffectPattern)) {
    imports.push({ specifier: match[1], typeOnly: false, index: statementIndex(match, "import") });
  }
  for (const match of source.matchAll(exportFromPattern)) {
    imports.push({
      specifier: match[3],
      typeOnly: Boolean(match[1]) || isTypeOnlyNamedClause(match[2].trim()),
      index: statementIndex(match, "export"),
    });
  }
  return imports;
}

function statementIndex(match, keyword) {
  return (match.index ?? 0) + match[0].indexOf(keyword);
}

function isTypeOnlyImportClause(clause) {
  if (!clause) return false;
  if (clause.startsWith("type ")) return true;
  if (!clause.startsWith("{")) return false;
  if (!clause.endsWith("}")) return false;

  return isTypeOnlyNamedClause(clause);
}

function isTypeOnlyNamedClause(clause) {
  if (!clause.startsWith("{") || !clause.endsWith("}")) return false;
  const specifiers = clause.slice(1, -1).split(",").map((entry) => entry.trim()).filter(Boolean);
  return specifiers.length > 0 && specifiers.every((specifier) => specifier.startsWith("type "));
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
  const segments = path.split("/").filter(Boolean);
  return segments.includes("__tests__") || /\.(?:test|spec)\.[cm]?[jt]sx?$/.test(file) || /\.d\.[cm]?ts$/.test(file);
}

export function missingSourceRoots(roots) {
  return roots.filter((root) => !existsSync(root));
}
