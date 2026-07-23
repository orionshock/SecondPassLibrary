import type { LibraryAuthor, Page } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { AuthorRowComponent } from "../components/AuthorRowComponent";

export function AuthorListPageRegion({ page, pageNumber, pageSize, loading, error, searching, libraryPath, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<LibraryAuthor>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  searching: boolean;
  libraryPath: string;
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
      ? <p className="library-list-state muted">{searching ? "No authors match this search." : "No authors."}</p>
      : <div className="library-axis-list-region__rows">{page.items.map((author) => <AuthorRowComponent key={author.id} author={author} libraryPath={libraryPath} />)}</div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Authors" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
