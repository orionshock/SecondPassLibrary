import {
  normalizeDateISO,
  normalizeOptionalString,
  normalizeSeriesIndex,
} from "./shared.js";

export function applyBookToMetadataForm({ book, dom, selectedAuthors }) {
  dom.titleEl.value = book.title || "";
  dom.subtitleEl.value = book.subtitle != null ? String(book.subtitle) : "";
  dom.descriptionEl.value = book.description || "";
  dom.publisherEl.value = book.publisher || "";
  dom.languageEl.value = book.language || "";
  const year = book.published_year != null ? String(book.published_year).padStart(4, "0") : "";
  const month = book.published_month != null ? String(book.published_month).padStart(2, "0") : "";
  const day = book.published_day != null ? String(book.published_day).padStart(2, "0") : "";
  const precision = book.published_date_precision || "";
  dom.publishedDateEl.value =
    precision === "day" && year && month && day
      ? `${year}-${month}-${day}`
      : precision === "month" && year && month
        ? `${year}-${month}`
        : precision === "year" && year
          ? year
          : "";
  const seriesIndex = book.series && book.series.series_index != null ? book.series.series_index : "";
  dom.seriesIndexEl.value = seriesIndex !== "" ? String(seriesIndex) : "";
  // selectedAuthors is tracked separately, but callers typically refresh it from book.authors before calling this.
}

export function buildBookPatchPayload({ dom, selectedAuthors, identifiers, catalogTags }) {
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

  const dateParts = publishedDate
    ? publishedDate.split("-").map((part) => Number(part))
    : [];

  return {
    payload: {
      title,
      subtitle: (dom.subtitleEl.value || "").trim(),
      description: normalizeOptionalString(dom.descriptionEl.value) || "",
      publisher: normalizeOptionalString(dom.publisherEl.value) || "",
      language: normalizeOptionalString(dom.languageEl.value) || "",
      published_year: dateParts.length ? dateParts[0] : null,
      published_month: dateParts.length >= 2 ? dateParts[1] : null,
      published_day: dateParts.length >= 3 ? dateParts[2] : null,
      published_date_precision:
        dateParts.length === 3 ? "day" : dateParts.length === 2 ? "month" : dateParts.length === 1 ? "year" : "",
      authors: selectedAuthors.map((a) => String(a.id)).filter(Boolean),
      series: dom.seriesSelectEl.value ? String(dom.seriesSelectEl.value) : null,
      series_index: seriesIndex,
      identifiers: identifiers.map((identifier) => ({
        scheme: String(identifier.scheme || "").trim(),
        value: String(identifier.value || "").trim(),
      })),
      catalog_tags: catalogTags.map((tag) => String(tag.name || "").trim()).filter(Boolean),
    },
  };
}
