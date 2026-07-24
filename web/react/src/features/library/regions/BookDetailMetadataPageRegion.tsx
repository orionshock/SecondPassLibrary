import type { BookDetail } from "@second-pass/spl-api";

import { BookIdentifierListComponent } from "../components/BookIdentifierListComponent";
import { formatBookFileSize, formatBookPublishedDate } from "../bookDetailPresentation";

export function BookDetailMetadataPageRegion({
  book,
  advancedGroupsEnabled,
}: {
  book: BookDetail;
  advancedGroupsEnabled: boolean;
}) {
  const publishedDate = formatBookPublishedDate(book);
  const fileSize = book.file ? formatBookFileSize(book.file.fileSize) : undefined;
  const hasBibliographicFacts = Boolean(book.publisher || book.language || publishedDate);

  return <section className="book-detail-metadata-region" aria-label="Book metadata">
    {hasBibliographicFacts ? <section className="book-detail-metadata-region__panel">
      <h2>Metadata</h2>
      <dl>
        {book.publisher ? <div><dt>Publisher</dt><dd>{book.publisher}</dd></div> : null}
        {book.language ? <div><dt>Language</dt><dd>{book.language}</dd></div> : null}
        {publishedDate ? <div><dt>Published</dt><dd>{publishedDate}</dd></div> : null}
      </dl>
    </section> : null}

    <section className="book-detail-metadata-region__panel">
      <h2>EPUB File</h2>
      {book.file ? <dl>
        <div><dt>Format</dt><dd>{book.file.format.toUpperCase()}</dd></div>
        {fileSize ? <div><dt>Size</dt><dd>{fileSize}</dd></div> : null}
      </dl> : <p className="book-detail-metadata-region__repair-state">This book’s EPUB file is unavailable.</p>}
    </section>

    {book.identifiers.length > 0 ? <section className="book-detail-metadata-region__panel">
      <h2>Identifiers</h2>
      <BookIdentifierListComponent identifiers={book.identifiers} />
    </section> : null}

    {advancedGroupsEnabled ? <section className="book-detail-metadata-region__panel">
      <h2>Visible Groups</h2>
      {book.groups.length > 0 ? <ul className="book-detail-metadata-region__groups">
        {book.groups.map((group) => <li key={group.id}>
          <span>{group.name}{group.isPublicGroup ? " (Public)" : ""}</span>
          {group.description ? <small>{group.description}</small> : null}
        </li>)}
      </ul> : <p className="muted">No visible groups.</p>}
    </section> : null}
  </section>;
}
