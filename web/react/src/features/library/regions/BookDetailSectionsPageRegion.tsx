import type { BookDetail, BookGroupSummary, BookPreview, ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { ErrorPanel } from "../../../components/ui";
import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";
import type { BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";
import { ShelfSummaryRowComponent, type ShelfOwnerBadge } from "../../../shared/shelves/ShelfSummaryRowComponent";
import { TabListComponent, tabButtonId, tabPanelId, type TabItem } from "../../../shared/tabs/TabListComponent";
import { BookIdentifierListComponent } from "../components/BookIdentifierListComponent";
import { formatBookFileSize, formatBookPublishedDate } from "../bookDetailPresentation";
import type { BookDetailTab } from "../bookTabs";

export type BookShelvesState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "ready"; shelves: ShelfSummary[] }
  | { status: "error"; error: Error };

export function BookDetailSectionsPageRegion({
  book,
  advancedGroupsEnabled,
  activeSection,
  shelvesState = { status: "idle" },
  shelfNavigationState,
  shelfBookNavigationState,
  groupNavigationState,
  onSectionChange,
  onRetryShelves,
}: {
  book: BookDetail;
  advancedGroupsEnabled: boolean;
  activeSection: BookDetailTab;
  shelvesState?: BookShelvesState;
  shelfNavigationState?: (shelf: ShelfSummary) => unknown;
  shelfBookNavigationState?: (shelf: ShelfSummary, book: BookPreview) => unknown;
  groupNavigationState?: (group: BookGroupSummary) => unknown;
  onSectionChange: (section: BookDetailTab) => void;
  onRetryShelves?: () => void;
}) {
  const sections: readonly TabItem<BookDetailTab>[] = [
    { id: "shelves", label: "Shelves" },
    ...(advancedGroupsEnabled ? [{ id: "groups" as const, label: "Groups" }] : []),
    { id: "metadata", label: "Metadata" },
  ];

  return <BookDetailSectionsComponent
    book={book}
    sections={sections}
    activeSection={activeSection}
    onSectionChange={onSectionChange}
    shelvesState={shelvesState}
    shelfNavigationState={shelfNavigationState}
    shelfBookNavigationState={shelfBookNavigationState}
    groupNavigationState={groupNavigationState}
    onRetryShelves={onRetryShelves}
  />;
}

function BookDetailSectionsComponent({
  book,
  sections,
  activeSection,
  onSectionChange,
  shelvesState,
  shelfNavigationState,
  shelfBookNavigationState,
  groupNavigationState,
  onRetryShelves,
}: {
  book: BookDetail;
  sections: readonly TabItem<BookDetailTab>[];
  activeSection: BookDetailTab;
  onSectionChange: (section: BookDetailTab) => void;
  shelvesState: BookShelvesState;
  shelfNavigationState?: (shelf: ShelfSummary) => unknown;
  shelfBookNavigationState?: (shelf: ShelfSummary, book: BookPreview) => unknown;
  groupNavigationState?: (group: BookGroupSummary) => unknown;
  onRetryShelves?: () => void;
}) {
  return <section className="book-detail-sections-region" aria-label="Book relationships and metadata">
    <TabListComponent tabs={sections} activeTab={activeSection} onChange={onSectionChange} ariaLabel="Book detail sections" idPrefix="book-detail" />
    <div
      className="book-detail-sections-region__panel"
      id={tabPanelId("book-detail", activeSection)}
      role="tabpanel"
      aria-labelledby={tabButtonId("book-detail", activeSection)}
    >
      {activeSection === "shelves" ? <BookDetailShelvesSection state={shelvesState} shelfNavigationState={shelfNavigationState} shelfBookNavigationState={shelfBookNavigationState} onRetry={onRetryShelves} /> : null}
      {activeSection === "groups" ? <BookDetailGroupsSection book={book} groupNavigationState={groupNavigationState} /> : null}
      {activeSection === "metadata" ? <BookDetailMetadataSection book={book} /> : null}
    </div>
  </section>;
}

function BookDetailShelvesSection({ state, shelfNavigationState, shelfBookNavigationState, onRetry }: {
  state: BookShelvesState;
  shelfNavigationState?: (shelf: ShelfSummary) => unknown;
  shelfBookNavigationState?: (shelf: ShelfSummary, book: BookPreview) => unknown;
  onRetry?: () => void;
}) {
  if (state.status === "idle" || state.status === "loading") {
    return <p className="muted" aria-busy="true">Loading shelves…</p>;
  }
  if (state.status === "error") {
    return <div className="book-detail-sections-region__shelves-error">
      <ErrorPanel>{state.error.message}</ErrorPanel>
      <button type="button" onClick={onRetry}>Retry</button>
    </div>;
  }
  if (state.shelves.length === 0) return <p className="muted">No visible shelves contain this book.</p>;

  return <div className="book-detail-sections-region__shelves">
    {state.shelves.map((shelf) => {
      const previewBooks: BookCoverPreviewItem[] = (shelf.previewBooks ?? []).map((preview) => ({
        ...preview,
        href: `/library/books/${encodeURIComponent(preview.id)}`,
        navigationState: shelfBookNavigationState?.(shelf, preview),
      }));
      const owner: ShelfOwnerBadge | undefined = shelf.ownerType === "group" && shelf.ownerGroup
        ? { kind: "group", label: shelf.ownerGroup.name, isPublicGroup: shelf.ownerGroup.isPublicGroup }
        : shelf.visibility === "listed" && shelf.ownerUser
          ? { kind: "user", label: `@${shelf.ownerUser.username}` }
          : undefined;
      return <ShelfSummaryRowComponent
        key={shelf.id}
        name={shelf.name}
        description={shelf.description}
        detailPath={`/shelves/${encodeURIComponent(shelf.id)}`}
        navigationState={shelfNavigationState?.(shelf)}
        previewBooks={previewBooks}
        owner={owner}
      />;
    })}
  </div>;
}

function BookDetailGroupsSection({ book, groupNavigationState }: {
  book: BookDetail;
  groupNavigationState?: (group: BookGroupSummary) => unknown;
}) {
  if (book.groups.length === 0) return <p className="muted">No visible groups.</p>;
  return <ul className="book-detail-sections-region__groups" aria-label="Book groups">
    {book.groups.map((group) => <li key={group.id} title={group.description || undefined}>
      <Link to={`/groups/${encodeURIComponent(group.id)}`} state={groupNavigationState?.(group)}>
        <GroupBadgeComponent name={group.name} isPublicGroup={group.isPublicGroup} size="medium" />
      </Link>
    </li>)}
  </ul>;
}

function BookDetailMetadataSection({ book }: { book: BookDetail }) {
  const publishedDate = formatBookPublishedDate(book);
  const fileSize = book.file ? formatBookFileSize(book.file.fileSize) : undefined;

  return <div className="book-detail-sections-region__metadata">
    <section className="book-detail-sections-region__metadata-panel">
      <h2>Metadata</h2>
      <dl>
        {book.publisher ? <div><dt>Publisher</dt><dd>{book.publisher}</dd></div> : null}
        {book.language ? <div><dt>Language</dt><dd>{book.language}</dd></div> : null}
        <div><dt>Published date</dt><dd>{publishedDate ?? "-"}</dd></div>
      </dl>
    </section>
    {book.file ? <section className="book-detail-sections-region__metadata-panel">
      <h2>File</h2>
      <dl>
        <div><dt>Format</dt><dd>{book.file.format.toUpperCase()}</dd></div>
        {fileSize ? <div><dt>Size</dt><dd>{fileSize}</dd></div> : null}
        {book.file.checksum ? <div><dt>Checksum</dt><dd>{book.file.checksum}</dd></div> : null}
      </dl>
    </section> : null}
    {book.identifiers.length > 0 ? <section className="book-detail-sections-region__metadata-panel">
      <h2>Identifiers</h2>
      <BookIdentifierListComponent identifiers={book.identifiers} />
    </section> : null}
  </div>;
}
