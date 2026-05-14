import {
  normalizeDateISO,
  normalizeOptionalString,
  normalizeSeriesIndex,
  normalizeSubjects,
  subjectsToTextareaValue,
} from "./shared.js";

export function applyBookToMetadataForm({ book, dom, selectedAuthors }) {
  dom.titleEl.value = book.title || "";
  dom.subtitleEl.value = book.subtitle != null ? String(book.subtitle) : "";
  dom.summaryEl.value = book.summary || "";
  dom.publisherEl.value = book.publisher || "";
  dom.languageEl.value = book.language || "";
  dom.publishedDateEl.value = book.published_date || "";
  dom.isbnEl.value = book.isbn || "";
  dom.subjectsEl.value = subjectsToTextareaValue(book.subjects);
  dom.seriesIndexEl.value = book.series_index != null && book.series_index !== "" ? String(book.series_index) : "";
  // selectedAuthors is tracked separately, but callers typically refresh it from book.authors before calling this.
}

export function buildBookPatchPayload({ dom, selectedAuthors }) {
  const title = (dom.titleEl.value || "").trim();
  if (!title) return { error: "Title is required." };

  const publishedDate = normalizeDateISO(dom.publishedDateEl.value);
  if (publishedDate && typeof publishedDate === "object" && publishedDate.error) {
    return { error: publishedDate.error };
  }

  const seriesIndex = normalizeSeriesIndex(dom.seriesIndexEl.value);
  if (seriesIndex && typeof seriesIndex === "object" && seriesIndex.error) {
    return { error: seriesIndex.error };
  }

  return {
    payload: {
      title,
      subtitle: (dom.subtitleEl.value || "").trim(),
      summary: normalizeOptionalString(dom.summaryEl.value),
      publisher: normalizeOptionalString(dom.publisherEl.value),
      language: normalizeOptionalString(dom.languageEl.value),
      published_date: publishedDate,
      isbn: normalizeOptionalString(dom.isbnEl.value),
      subjects: normalizeSubjects(dom.subjectsEl.value),
      authors: selectedAuthors.map((a) => String(a.id)).filter(Boolean),
      series: dom.seriesSelectEl.value ? String(dom.seriesSelectEl.value) : null,
      series_index: seriesIndex,
    },
  };
}

