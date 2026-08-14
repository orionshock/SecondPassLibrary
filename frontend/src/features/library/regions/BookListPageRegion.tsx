import type { CompactBook, Page } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { CompactBookRow } from "../../../shared/books/CompactBookRow";
import { Pager } from "../../../shared/pagination/Pager";
import { bookBrowseDetailBreadcrumbs } from "../bookDetailPresentation";

export function BookListPageRegion({ page, pageNumber, pageSize, loading, error, searching = false, tagged = false, selectedContext, libraryPath, parentLibraryPath, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<CompactBook>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  searching?: boolean;
  tagged?: boolean;
  selectedContext?: { kind: "author" | "series"; label: string };
  libraryPath: string;
  parentLibraryPath?: string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="book-list-state" aria-live="polite" aria-busy="true">Loading books...</section>;
  if (!page && error) return <section className="book-list-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`book-list-region${loading ? " book-list-region--loading" : ""}`} aria-label="Books" aria-busy={loading}>
    {error ? <div className="book-list-region__inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0
      ? <p className="book-list-state muted">{bookEmptyCopy(searching, tagged, selectedContext?.kind)}</p>
      : <div className="book-list-region__rows">{page.items.map((book) => {
        const detailPath = `/library/books/${encodeURIComponent(book.id)}`;
        const navigationState = breadcrumbNavigationState(bookBrowseDetailBreadcrumbs({
          title: book.title,
          libraryPath,
          contextLabel: selectedContext?.label,
          contextKind: selectedContext?.kind,
          parentLibraryPath: parentLibraryPath ?? libraryPath,
        }));
        return <CompactBookRow key={book.id} book={book} detailPath={detailPath} navigationState={navigationState} />;
      })}</div>}
    <Pager
      page={pageNumber}
      pageSize={pageSize}
      count={page.count}
      hasPrevious={Boolean(page.previous)}
      hasNext={Boolean(page.next)}
      itemLabel="Books"
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    />
  </section>;
}

export function bookEmptyCopy(searching: boolean, tagged: boolean, selectedContext?: "author" | "series"): string {
  if (selectedContext) {
    const entity = selectedContext === "author" ? "author" : "series";
    if (searching && tagged) return `No books match this search for this ${entity} within this Catalog Tag.`;
    if (searching) return `No books match this search for this ${entity}.`;
    if (tagged) return `No books found for this ${entity} within this Catalog Tag.`;
    return `No books found for this ${entity}.`;
  }
  if (searching && tagged) return "No books match this search within this Catalog Tag.";
  if (searching) return "No books match this search.";
  if (tagged) return "No books for this Catalog Tag.";
  return "No books.";
}
