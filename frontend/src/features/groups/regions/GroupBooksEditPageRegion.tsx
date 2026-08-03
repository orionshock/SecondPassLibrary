import type { CompactBook, Page } from "@second-pass/spl-api";

import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, ErrorPanel } from "../../../components/ui";
import { CompactBookRowComponent } from "../../../shared/books/CompactBookRowComponent";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { groupBookBreadcrumbs } from "../groupsBreadcrumbs";

export function GroupBooksEditPageRegion({ groupId, groupName, isPublicGroup, page, pageNumber, pageSize, loading, error, pendingBookId, controlsDisabled, onRemove, onPageChange, onPageSizeChange, onRetry }: {
  groupId: string;
  groupName: string;
  isPublicGroup?: boolean;
  page?: Page<CompactBook>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  pendingBookId?: string;
  controlsDisabled?: boolean;
  onRemove: (book: CompactBook) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="group-edit-section-state" aria-live="polite" aria-busy="true">Loading books...</section>;
  if (!page && error) return <section className="group-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className="group-books-edit-region" aria-label="Assigned group books" aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="muted">This group has no books.</p> : <div className="group-book-rows">
      {page.items.map((book) => <CompactBookRowComponent
        key={book.id}
        book={book}
        detailPath={`/library/books/${encodeURIComponent(book.id)}`}
        navigationState={breadcrumbNavigationState(groupBookBreadcrumbs(groupId, groupName, book.title, undefined, isPublicGroup))}
        actions={<RemoveIconButton
          type="button"
          label={`Remove ${book.title} from group`}
          title={pendingBookId === book.id ? "Removing" : "Remove from group"}
          disabled={controlsDisabled || Boolean(pendingBookId)}
          onClick={() => onRemove(book)}
        />}
      />)}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Books" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
