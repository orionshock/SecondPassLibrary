import type { LibraryImportResult } from "@second-pass/spl-api";

import { Badge, Surface } from "../../../components/ui";
import {
  ImportResultItemComponent,
  type ImportResultBookNavigation,
} from "../components/ImportResultItemComponent";

const countKeys = ["imported", "duplicate", "conflict", "failed", "skipped"] as const;

export function ImportResultPageRegion({ result, bookNavigation }: {
  result?: LibraryImportResult;
  bookNavigation?: (bookId: string, title: string) => ImportResultBookNavigation;
}) {
  return <Surface title="Latest result">
    {!result ? <p className="muted">No import has been run in this browser session.</p> : <>
      <div className="import-result-summary">
        <strong>{result.sourceLabel}</strong>
        <Badge>{result.sourceType}</Badge>
        <div className="import-result-counts">{countKeys.map((key) => <Badge key={key} tone={key === "imported" ? "success" : "default"}>{key}: {result.counts[key]}</Badge>)}</div>
      </div>
      <ol className="import-result-list">{result.items.map((item, index) => <ImportResultItemComponent
        key={`${item.sourceLabel}-${index}`}
        item={item}
        bookNavigation={item.bookId ? bookNavigation?.(item.bookId, item.title || item.sourceLabel) : undefined}
      />)}</ol>
    </>}
  </Surface>;
}
