import type { BookDetail, ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { ErrorPanel } from "../../../components/ui";
import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";
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
  onSectionChange,
  onRetryShelves,
}: {
  book: BookDetail;
  advancedGroupsEnabled: boolean;
  activeSection: BookDetailTab;
  shelvesState?: BookShelvesState;
  shelfNavigationState?: (shelfName: string) => unknown;
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
  onRetryShelves,
}: {
  book: BookDetail;
  sections: readonly TabItem<BookDetailTab>[];
  activeSection: BookDetailTab;
  onSectionChange: (section: BookDetailTab) => void;
  shelvesState: BookShelvesState;
  shelfNavigationState?: (shelfName: string) => unknown;
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
      {activeSection === "shelves" ? <BookDetailShelvesSection state={shelvesState} shelfNavigationState={shelfNavigationState} onRetry={onRetryShelves} /> : null}
      {activeSection === "groups" ? <BookDetailGroupsSection book={book} /> : null}
      {activeSection === "metadata" ? <BookDetailMetadataSection book={book} /> : null}
    </div>
  </section>;
}

function BookDetailShelvesSection({ state, shelfNavigationState, onRetry }: {
  state: BookShelvesState;
  shelfNavigationState?: (shelfName: string) => unknown;
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

  return <ul className="book-detail-sections-region__shelves">
    {state.shelves.map((shelf) => <li key={shelf.id}>
      <strong><Link
        to={`/shelves/${encodeURIComponent(shelf.id)}`}
        state={shelfNavigationState?.(shelf.name)}
      >{shelf.name}</Link></strong>
      <div className="book-detail-sections-region__shelf-facts">
        {shelf.ownerType === "user" && shelf.visibility === "listed" && shelf.ownerUser
          ? <span>Shared by @{shelf.ownerUser.username}</span>
          : null}
        {shelf.ownerType === "user" ? <span>{shelf.visibility === "listed" ? "Listed" : "Private"}</span> : null}
        {shelf.ownerType === "group" && shelf.ownerGroup ? <GroupBadgeComponent name={shelf.ownerGroup.name} isPublicGroup={shelf.ownerGroup.isPublicGroup} /> : null}
        <span>{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
      </div>
    </li>)}
  </ul>;
}

function BookDetailGroupsSection({ book }: { book: BookDetail }) {
  if (book.groups.length === 0) return <p className="muted">No visible groups.</p>;
  return <ul className="book-detail-sections-region__groups">
    {book.groups.map((group) => <li key={group.id} title={group.description || undefined}>
      <GroupBadgeComponent name={group.name} isPublicGroup={group.isPublicGroup} />
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
