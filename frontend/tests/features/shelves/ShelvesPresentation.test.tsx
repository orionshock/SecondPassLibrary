import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { CompactBook, ShelfItem, ShelfItemOrdering, ShelfOrdering, ShelfSummary } from "@second-pass/spl-api";
import { ShelfHeaderPageRegion } from "../../../src/features/shelves/detail/ShelfHeaderPageRegion";
import { ShelfItemsPageRegion } from "../../../src/features/shelves/detail/ShelfItemsPageRegion";
import { ShelvesListPageRegion } from "../../../src/features/shelves/list/ShelvesListPageRegion";
import { ShelfScopesPageRegion } from "../../../src/features/shelves/list/ShelfScopesPageRegion";

const book: CompactBook = {
  id: "book", title: "Visible Book", sortTitle: "Visible Book", subtitle: "Not rendered",
  authors: [{ id: "author", name: "Visible Author" }], series: null, catalogTags: [],
  language: "eng", publisher: "Publisher", publishedYear: null, publishedMonth: null,
  publishedDay: null, publishedDatePrecision: "", coverUrl: null, fileFormat: "epub",
};
const personalShelf: ShelfSummary = {
  id: "shelf", name: "Favorites", description: "<b>Reader picks</b>", ownerType: "user",
  ownerUser: { profileId: "profile", username: "reader" }, ownerGroup: null,
  visibility: "listed", itemCount: 1, canEdit: false,
  previewBooks: [{ id: book.id, title: book.title, coverUrl: book.coverUrl }],
};
const groupShelf: ShelfSummary = {
  ...personalShelf,
  id: "group-shelf",
  ownerType: "group",
  ownerUser: null,
  ownerGroup: { id: "public", name: "Common Room", isPublicGroup: true },
  visibility: "private",
  itemCount: 0,
};
const item: ShelfItem = {
  id: "item", shelfId: "shelf", book, position: 0,
  addedBy: { profileId: "adder", username: "reader" },
};

describe("Shelves read-only regions", () => {
  it("renders all labelled, decorative-icon Shelf scopes", () => {
    const markup = renderToStaticMarkup(<ShelfScopesPageRegion activeScope="personal" onScopeChange={vi.fn()} />);
    expect(markup).toMatch(/aria-current="page"[^>]*><span[^>]*aria-hidden="true"[^>]*>shelves<\/span><span>Personal<\/span>/);
    expect(markup).toContain(">share</span><span>Shared by Others</span>");
    expect(markup).toContain(">group_work</span><span>Group Shelves</span>");
    expect(markup.match(/aria-current="page"/g)).toHaveLength(1);
    expect(markup.match(/aria-hidden="true"/g)).toHaveLength(3);
    expect(markup).not.toContain(">All<");
  });

  it("renders Shelf list identity, previews, and optional Group treatment without inline Edit", () => {
    const renderList = (shelf: ShelfSummary, scope: "personal" | "shared" | "group", ordering: ShelfOrdering = "name") => renderToStaticMarkup(<MemoryRouter><ShelvesListPageRegion
      page={{ items: [shelf], count: 1, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      scope={scope}
      ordering={ordering}
      loading={false}
      onScopeChange={vi.fn()}
      onOrderingChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    const personal = renderList(personalShelf, "personal");
    expect(personal).toContain('href="/shelves/shelf"');
    expect(personal).toContain("Favorites");
    expect(personal).toContain("&lt;b&gt;Reader picks&lt;/b&gt;");
    expect(personal).toContain('aria-label="Open Visible Book"');
    expect(personal).toContain('aria-label="Shelves pagination, top"');
    expect(personal).toContain('aria-label="Shelves pagination, bottom"');
    expect(personal).toContain('aria-label="Order shelves, current: Name A-Z"');
    expect(personal).not.toContain('href="/shelves/shelf/edit"');
    expect(personal).not.toContain('aria-label="User reader"');

    expect(renderList(personalShelf, "personal", "-name")).toContain("Name Z-A");
    expect(renderList(personalShelf, "personal", "-item_count")).toContain("Most Items");
    expect(renderList(personalShelf, "personal", "item_count")).toContain("Fewest Items");

    const group = renderList(groupShelf, "group");
    expect(group).toContain('aria-label="Public group: Common Room"');
    expect(group).not.toContain('href="/shelves/group-shelf/edit"');

    const shared = renderList(personalShelf, "shared");
    expect(shared).toContain('aria-label="User reader"');
    expect(shared).not.toContain("@reader");
    expect(shared).toContain('href="/shelves/shelf"');
    expect(shared).not.toContain('href="/shelves/shelf/edit"');
  });

  it("renders a read-only detail header and compact Book rows", () => {
    const header = renderToStaticMarkup(<ShelfHeaderPageRegion shelf={personalShelf} loading={false} onRetry={vi.fn()} />);
    expect(header).toContain("Favorites");
    expect(header).toContain("Shared by");
    expect(header).toContain('aria-label="User reader"');
    expect(header).not.toContain("@reader");
    expect(header).not.toContain("Edit");

    const renderItems = (ordering: ShelfItemOrdering) => renderToStaticMarkup(<MemoryRouter><ShelfItemsPageRegion
      shelfId="shelf"
      shelfName="Favorites"
      scope="personal"
      shelfPath="/shelves/shelf?ordering=title"
      page={{ items: [item], count: 1, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      ordering={ordering}
      loading={false}
      onOrderingChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    const items = renderItems("position");
    expect(items).toContain("Visible Book");
    expect(items).toContain('href="/library/books/book"');
    expect(items).toContain('aria-label="Order shelf books, current: Shelf Order"');
    expect(items).not.toContain("adder");
    for (const absent of ["Add book", "Remove book", "Move up", "Move down"]) expect(items).not.toContain(absent);
    expect(renderItems("-position")).toContain("Reverse Shelf Order");
    expect(renderItems("-title")).toContain("Title Z-A");
    expect(renderItems("-author")).toContain("Author Z-A");
  });
});

