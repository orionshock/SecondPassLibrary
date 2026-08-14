import type { LibraryAuthor, Page } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";
import { Pager } from "../../../shared/pagination/Pager";
import { AuthorRow } from "../components/AuthorRow";

export function AuthorListPageRegion({ page, pageNumber, pageSize, loading, error, searching, tagged, libraryPath, contextPathFor, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<LibraryAuthor>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  searching: boolean;
  tagged: boolean;
  libraryPath: string;
  contextPathFor: (author: LibraryAuthor) => string;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="library-list-state" aria-live="polite" aria-busy="true">Loading authors...</section>;
  if (!page && error) return <section className="library-list-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;
  return <section className={`library-axis-list-region${loading ? " library-axis-list-region--loading" : ""}`} aria-label="Authors" aria-busy={loading}>
    {error ? <div className="library-list-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0
      ? <p className="library-list-state muted">{authorEmptyCopy(searching, tagged)}</p>
      : <div className="library-axis-list-region__rows">{page.items.map((author) => <AuthorRow key={author.id} author={author} libraryPath={libraryPath} contextPath={contextPathFor(author)} />)}</div>}
    <Pager page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Authors" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}

export function authorEmptyCopy(searching: boolean, tagged: boolean): string {
  if (searching && tagged) return "No authors match this search within this Catalog Tag.";
  if (searching) return "No authors match this search.";
  if (tagged) return "No authors for this Catalog Tag.";
  return "No authors.";
}
