import type { LibraryImportItem } from "@second-pass/spl-api";

export function ImportResultItemComponent({ item }: { item: LibraryImportItem }) {
  const detailed = item.status !== "imported";
  const label = item.title || item.sourceLabel;

  return <li className={`import-result-item import-result-item--${item.status}`}>
    <div className="import-result-item__summary">
      <span className={`import-status import-status--${item.status}`}>{item.status}</span>
      <strong>{label}</strong>
      {item.authors?.length ? <span>{item.authors.join(", ")}</span> : null}
      {item.series ? <span>{item.series}{item.seriesIndex ? ` ${item.seriesIndex}` : ""}</span> : null}
    </div>
    {detailed ? <div className="import-result-item__detail">
      <span>Source: {item.sourceLabel}</span>
      <span>{item.safeMessage || "No additional safe detail was provided."}</span>
    </div> : null}
  </li>;
}
