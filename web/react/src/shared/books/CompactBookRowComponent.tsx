import { Link } from "react-router";
import type { ReactNode } from "react";

import { BookCoverComponent } from "./BookCoverComponent";
import { BookMetadataComponent } from "./BookMetadataComponent";

export interface CompactBookRowData {
  id: string;
  title: string;
  authors: ReadonlyArray<{ name: string }>;
  series: { name: string; seriesIndex: string | null } | null;
  catalogTags?: ReadonlyArray<{ id: string; name: string }>;
  publisher?: string;
  coverUrl: string | null;
}

export function CompactBookRowComponent({
  book,
  detailPath,
  navigationState,
  details,
  actions,
}: {
  book: CompactBookRowData;
  detailPath?: string;
  navigationState?: unknown;
  details?: ReactNode;
  actions?: ReactNode;
}) {
  const catalogTags = book.catalogTags ?? [];
  const tags = catalogTags.slice(0, 6);
  const hiddenCount = Math.max(0, catalogTags.length - tags.length);
  const series = book.series
    ? `${book.series.name}${book.series.seriesIndex ? ` ${book.series.seriesIndex}` : ""}`
    : undefined;

  return <article className="book-row-component">
    {detailPath ? <Link className="book-row-component__cover-link" to={detailPath} state={navigationState} aria-label={`Open ${book.title}`}>
      <BookCoverComponent coverUrl={book.coverUrl} title={book.title} />
    </Link> : <div className="book-row-component__cover-link"><BookCoverComponent coverUrl={book.coverUrl} title={book.title} /></div>}
    <div className="book-row-component__body">
      <h2>{detailPath ? <Link to={detailPath} state={navigationState}>{book.title}</Link> : book.title}</h2>
      <BookMetadataComponent
        authors={book.authors.map(({ name }) => name)}
        series={series}
        publisher={book.publisher || undefined}
      />
      {details}
      {tags.length > 0 ? <div className="book-row-component__tags" aria-label="Catalog Tags">
        {tags.map((tag) => <span className="book-row-component__tag" key={tag.id}>{tag.name}</span>)}
        {hiddenCount > 0 ? <span className="book-row-component__tag book-row-component__tag--more">+{hiddenCount}</span> : null}
      </div> : null}
    </div>
    {actions ? <div className="book-row-component__actions">{actions}</div> : null}
  </article>;
}
