import { escapeHtml } from "../layout.js";

const BOOK_METADATA_FIELDS = [
  { key: "authors", label: "Author", icon: "person" },
  { key: "series", label: "Series", icon: "auto_stories" },
  { key: "publisher", label: "Publisher", icon: "apartment" },
];

function publishedYear(value) {
  const raw = value == null ? "" : String(value).trim();
  if (!raw) return "";
  const match = raw.match(/\d{4}/);
  return match ? match[0] : raw;
}

export function bookMetadataItems(book) {
  const value = book || {};
  const authors = Array.isArray(value.authors)
    ? value.authors.map((author) => author && author.name).filter(Boolean).join(", ")
    : "";
  const seriesName = value.series && value.series.name ? String(value.series.name) : "";
  const rawSeriesIndex = value.series_index != null && value.series_index !== ""
    ? value.series_index
    : value.series && value.series.series_index;
  const seriesIndex = rawSeriesIndex != null && rawSeriesIndex !== ""
    ? String(rawSeriesIndex)
    : "";
  const series = seriesName ? `${seriesName}${seriesIndex ? ` ${seriesIndex}` : ""}` : "";
  const publisher = value.publisher ? String(value.publisher).trim() : "";
  const year = publishedYear(value.published_date);
  const values = {
    authors,
    series,
    publisher: [publisher, year].filter(Boolean).join(" "),
  };

  return BOOK_METADATA_FIELDS
    .map((field) => ({ ...field, value: values[field.key] }))
    .filter((field) => field.value);
}

export function renderBookMetadataHtml(book, { emptyText = "" } = {}) {
  const items = bookMetadataItems(book);
  if (!items.length) return emptyText ? `<span class="muted">${escapeHtml(emptyText)}</span>` : "";
  return items.map((item) => `
    <span class="book-metadata__item">
      <span class="material-symbols-outlined book-metadata__icon" aria-hidden="true">${item.icon}</span>
      <span class="sr-only">${item.label}: </span>
      <span class="book-metadata__value">${escapeHtml(item.value)}</span>
    </span>
  `.trim()).join("");
}
