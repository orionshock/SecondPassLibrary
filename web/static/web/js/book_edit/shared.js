import { fetchJSON } from "../api.js";

export function clear(node) {
  if (!node) return;
  while (node.firstChild) node.removeChild(node.firstChild);
}

export function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined && text !== null) node.textContent = String(text);
  return node;
}

export function normalizeOptionalString(value) {
  const s = value == null ? "" : String(value);
  const trimmed = s.trim();
  return trimmed ? trimmed : null;
}

export function normalizeDateISO(value) {
  const s = normalizeOptionalString(value);
  if (!s) return null;
  if (/^\d{4}(-\d{2}){0,2}$/.test(s)) return s;
  return { error: "Published date must be YYYY, YYYY-MM, or YYYY-MM-DD." };
}

export function normalizeSeriesIndex(value) {
  const s = normalizeOptionalString(value);
  if (!s) return null;
  if (!/^\d+(\.\d)?$/.test(s)) {
    return { error: "Series index must be an integer or one decimal place (e.g. 5 or 5.1)." };
  }
  const n = Number.parseFloat(s);
  if (!Number.isFinite(n)) return { error: "Series index must be a number." };
  if (n < 0) return { error: "Series index must be >= 0." };
  return (Math.round(n * 10) / 10).toFixed(1);
}

export function normalizeSubjects(text) {
  const s = text == null ? "" : String(text);
  const raw = s
    .split(/\r?\n|,/g)
    .map((v) => v.trim())
    .filter(Boolean);
  const seen = new Set();
  const out = [];
  for (const item of raw) {
    const key = item.toLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    out.push(item);
  }
  return out;
}

export function subjectsToTextareaValue(subjects) {
  if (!subjects) return "";
  if (Array.isArray(subjects)) {
    return subjects
      .map((s) => String(s).trim())
      .filter(Boolean)
      .join("\n");
  }
  if (typeof subjects === "string") return subjects.trim();
  return "";
}

export async function fetchAllPages(url) {
  const out = [];
  let next = url;
  let safety = 0;
  while (next && safety < 50) {
    const payload = await fetchJSON(next);
    if (payload && Array.isArray(payload.results)) out.push(...payload.results);
    next = payload && payload.next ? payload.next : null;
    safety += 1;
  }
  return out;
}

export function uniqueById(items) {
  const seen = new Set();
  const out = [];
  for (const item of items || []) {
    const id = item && item.id != null ? String(item.id) : "";
    if (!id || seen.has(id)) continue;
    seen.add(id);
    out.push(item);
  }
  return out;
}

const IDENT_SCHEMES = [
  ["isbn_10", "ISBN-10"],
  ["isbn_13", "ISBN-13"],
  ["asin", "ASIN"],
  ["doi", "DOI"],
  ["oclc", "OCLC"],
  ["lccn", "LCCN"],
  ["openlibrary", "Open Library"],
  ["calibre", "Calibre"],
  ["epub_uid", "EPUB UID"],
  ["publisher", "Publisher"],
  ["uri", "URI/URN"],
  ["uuid", "UUID"],
  ["other", "Other"],
];

export function fillSchemeOptions(selectEl, selectedValue) {
  clear(selectEl);
  for (const [v, label] of IDENT_SCHEMES) {
    const opt = document.createElement("option");
    opt.value = v;
    opt.textContent = label;
    if (selectedValue && String(selectedValue) === v) opt.selected = true;
    selectEl.appendChild(opt);
  }
}
