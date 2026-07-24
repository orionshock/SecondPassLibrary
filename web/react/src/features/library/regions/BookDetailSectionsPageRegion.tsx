import type { BookDetail } from "@second-pass/spl-api";
import { useState } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge } from "../../../components/ui";
import { BookIdentifierListComponent } from "../components/BookIdentifierListComponent";
import { formatBookFileSize, formatBookPublishedDate } from "../bookDetailPresentation";

export type BookDetailSection = "shelves" | "groups" | "metadata";

export function BookDetailSectionsPageRegion({
  book,
  advancedGroupsEnabled,
  initialSection = "shelves",
}: {
  book: BookDetail;
  advancedGroupsEnabled: boolean;
  initialSection?: BookDetailSection;
}) {
  const allowedInitialSection = initialSection === "groups" && !advancedGroupsEnabled ? "shelves" : initialSection;
  const [activeSection, setActiveSection] = useState<BookDetailSection>(allowedInitialSection);
  const sections: Array<{ id: BookDetailSection; label: string }> = [
    { id: "shelves", label: "Shelves" },
    ...(advancedGroupsEnabled ? [{ id: "groups" as const, label: "Groups" }] : []),
    { id: "metadata", label: "Metadata" },
  ];

  return <BookDetailSectionsComponent
    book={book}
    sections={sections}
    activeSection={activeSection}
    onSectionChange={setActiveSection}
  />;
}

function BookDetailSectionsComponent({
  book,
  sections,
  activeSection,
  onSectionChange,
}: {
  book: BookDetail;
  sections: Array<{ id: BookDetailSection; label: string }>;
  activeSection: BookDetailSection;
  onSectionChange: (section: BookDetailSection) => void;
}) {
  return <section className="book-detail-sections-region" aria-label="Book relationships and metadata">
    <div className="book-detail-sections-region__tabs" role="tablist" aria-label="Book detail sections">
      {sections.map((section) => <button
        key={section.id}
        type="button"
        role="tab"
        id={`book-detail-${section.id}-tab`}
        aria-controls={`book-detail-${section.id}-panel`}
        aria-selected={activeSection === section.id}
        className={activeSection === section.id ? "active" : undefined}
        onClick={() => onSectionChange(section.id)}
      >{section.label}</button>)}
    </div>
    {sections.map((section) => <div
      key={section.id}
      className="book-detail-sections-region__panel"
      id={`book-detail-${section.id}-panel`}
      role="tabpanel"
      aria-labelledby={`book-detail-${section.id}-tab`}
      hidden={activeSection !== section.id}
    >
      {activeSection === section.id && section.id === "shelves" ? <p className="muted">Shelf relationships are not rebuilt yet.</p> : null}
      {activeSection === section.id && section.id === "groups" ? <BookDetailGroupsSection book={book} /> : null}
      {activeSection === section.id && section.id === "metadata" ? <BookDetailMetadataSection book={book} /> : null}
    </div>)}
  </section>;
}

function BookDetailGroupsSection({ book }: { book: BookDetail }) {
  if (book.groups.length === 0) return <p className="muted">No visible groups.</p>;
  return <ul className="book-detail-sections-region__groups">
    {book.groups.map((group) => <li key={group.id} title={group.description || undefined}>
      <Badge tone={group.isPublicGroup ? "success" : "default"}>
        {group.isPublicGroup ? <MaterialIcon name="public" size={15} /> : null}
        {group.name}
      </Badge>
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
