import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import type { CompactBook, LibraryGroup, ShelfSummary } from "@second-pass/spl-api";
import { GroupMemberRowComponent } from "../features/groups/components/GroupMemberRowComponent";
import { GroupBooksPageRegion } from "../features/groups/regions/GroupBooksPageRegion";
import { GroupHeaderPageRegion } from "../features/groups/regions/GroupHeaderPageRegion";
import { GroupMembersPageRegion } from "../features/groups/regions/GroupMembersPageRegion";
import { GroupShelvesPageRegion } from "../features/groups/regions/GroupShelvesPageRegion";
import { GroupsListPageRegion } from "../features/groups/regions/GroupsListPageRegion";
import { GroupRow } from "../shared/groups/GroupRow";

const group: LibraryGroup = {
  id: "group", name: "Common Room", description: "<b>Add, edit, and delete books</b>", isPublicGroup: true,
};
const book: CompactBook = {
  id: "book", title: "Visible Book", sortTitle: "Visible Book", subtitle: "Hidden",
  authors: [{ id: "author", name: "Visible Author" }], series: null, catalogTags: [],
  language: "eng", publisher: "Publisher", publishedYear: null, publishedMonth: null,
  publishedDay: null, publishedDatePrecision: "", coverUrl: null, fileFormat: "EPUB",
};

describe("Groups read-only regions", () => {
  it("renders server-driven Public and curator treatments without mutation controls or counts", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><GroupRow
      group={group}
      detailPath="/groups/group"
      isCurator
      previewBooks={[]}
    /></MemoryRouter>);
    expect(markup).toContain('href="/groups/group"');
    expect(markup).toContain("Public");
    expect(markup).toContain("Curator");
    expect(markup).toContain("&lt;b&gt;Add, edit, and delete books&lt;/b&gt;");
    expect(markup).not.toContain("<form");
    expect(markup).not.toContain('href="/groups/group/edit"');
    expect(markup).not.toContain('aria-label="Delete');
    expect(markup).not.toContain("1 Book");
  });

  it("keeps Group identity structurally primary beside the shared compact preview", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><GroupRow
      group={group}
      detailPath="/groups/group"
      isCurator={false}
      previewBooks={[{
        id: book.id, title: book.title, coverUrl: null, href: "/library/books/book",
      }]}
    /></MemoryRouter>);

    expect(markup).toContain("group-row-component compact-cover-preview-row");
    expect(markup).toContain("group-row-component__identity compact-cover-preview-row__primary");
    expect(markup).toContain("book-cover-preview-strip-component");
    expect(markup).toContain('href="/groups/group"');
    expect(markup).toContain('href="/library/books/book"');
  });

  it("renders all read-only Group detail sections", () => {
    const markup = renderToStaticMarkup(<GroupHeaderPageRegion
      group={group}
      loading={false}
      isCurator
      activeTab="books"
      onTabChange={vi.fn()}
      onRetry={vi.fn()}
    />);
    expect(markup).toContain("Books");
    expect(markup).toContain("Members");
    expect(markup).toContain("Shelves");
    expect(markup).toContain('role="tablist"');
    expect((markup.match(/role="tab"/g) ?? [])).toHaveLength(3);
    expect(markup).toContain('id="group-detail-books-tab"');
    expect(markup).toContain('aria-controls="group-detail-books-panel"');
    expect(markup).toContain('aria-selected="true"');
    expect(markup).not.toContain("href=");
  });

  it("renders authorized Group lifecycle destinations in the shared responsive action area", () => {
    const detail = renderToStaticMarkup(<MemoryRouter><GroupHeaderPageRegion
      group={{ ...group, isPublicGroup: false }}
      loading={false}
      isCurator={false}
      editPath="/groups/group/edit"
      createShelfPath="/shelves/new"
      createShelfNavigationState={{ source: "group" }}
      activeTab="shelves"
      onTabChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(detail).toContain('href="/groups/group/edit"');
    expect(detail).toContain('class="group-detail-header__actions"');
    expect(detail).toContain('class="button button--secondary group-detail-header__manage"');
    expect(detail).toContain('href="/shelves/new"');
    expect(detail).toContain('group-detail-header__create-shelf');
    expect(detail).toContain('aria-hidden="true"');
    expect(detail).toContain('>add</span>Create Shelf for Group</a>');

    const unauthorized = renderToStaticMarkup(<GroupHeaderPageRegion
      group={group}
      loading={false}
      isCurator={false}
      activeTab="shelves"
      onTabChange={vi.fn()}
      onRetry={vi.fn()}
    />);
    expect(unauthorized).not.toContain('group-detail-header__actions');

    const otherTab = renderToStaticMarkup(<MemoryRouter><GroupHeaderPageRegion
      group={group}
      loading={false}
      isCurator={false}
      createShelfPath="/shelves/new"
      activeTab="books"
      onTabChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(otherTab).not.toContain('href="/shelves/new"');

    const list = (canCreate: boolean) => renderToStaticMarkup(<MemoryRouter><GroupsListPageRegion
      page={{ items: [], count: 0, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      search=""
      ordering="name"
      loading={false}
      curatorGroupIds={new Set<string>()}
      canCreate={canCreate}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onOrderingChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(list(true)).toContain('href="/groups/new"');
    expect(list(false)).not.toContain('href="/groups/new"');
  });

  it("frames the main Group rows with lean top and full bottom pagination", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><GroupsListPageRegion
      page={{ items: [group], count: 21, next: "/next", previous: null }}
      pageNumber={1}
      pageSize={20}
      search="room"
      ordering="name"
      loading={false}
      curatorGroupIds={new Set<string>()}
      canCreate={false}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onOrderingChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="Groups pagination, top"');
    expect(markup).toContain('aria-label="Groups pagination, bottom"');
    expect(markup).toContain('aria-label="Order groups, current: Name A-Z"');
    expect(markup).toContain('value="room"');
    expect(markup).toContain("Name A-Z");
    expect(markup).toContain('href="/groups/group"');
  });

  it("reuses compact Book rows without assignment controls", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><GroupBooksPageRegion
      groupId="group"
      groupName="Readers"
      groupPath="/groups/group?q=visible"
      page={{ items: [book], count: 1, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      search=""
      ordering="title"
      loading={false}
      onSearchChange={vi.fn()}
      onSearch={vi.fn()}
      onOrderingChange={vi.fn()}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(markup).toContain("Visible Book");
    expect(markup).toContain('href="/library/books/book"');
    expect(markup).toContain('aria-label="Order group books, current: Title A-Z"');
    expect(markup).not.toContain("Remove book");
    expect(markup).not.toContain("Add book");
  });

  it("renders username and curator state without membership internals", () => {
    const membership = { user: { profileId: "profile", username: "reader" }, isCurator: true };
    const row = renderToStaticMarkup(<GroupMemberRowComponent membership={membership} />);
    expect(row).toContain('aria-label="User reader"');
    expect(row).not.toContain("@reader");
    expect(row).toContain("Curator");
    expect(row).not.toContain("profile");
    const list = renderToStaticMarkup(<GroupMembersPageRegion
      page={{ items: [membership], count: 1, next: null, previous: null }}
      pageNumber={1}
      pageSize={20}
      loading={false}
      onPageChange={vi.fn()}
      onPageSizeChange={vi.fn()}
      onRetry={vi.fn()}
    />);
    expect(list).not.toContain('aria-label="Remove');
    expect(list).not.toContain("<form");
    expect(list).not.toContain("email");
  });

  it("keeps Group Shelf rows browse-only and frames them with synchronized pagination", () => {
    const shelf: ShelfSummary = {
      id: "shelf/id", name: "Favorites", description: "Shared picks", ownerType: "group",
      ownerUser: null, ownerGroup: { id: group.id, name: group.name, isPublicGroup: true },
      visibility: "private", itemCount: 3, canEdit: true,
      previewBooks: [{ id: book.id, title: book.title, coverUrl: book.coverUrl }],
    };
    const props = {
      groupId: group.id, groupName: group.name, groupPath: "/groups/group?tab=shelves",
      pageNumber: 1, pageSize: 20, loading: false, onPageChange: vi.fn(),
      onPageSizeChange: vi.fn(), onRetry: vi.fn(),
    };
    const markup = renderToStaticMarkup(<MemoryRouter><GroupShelvesPageRegion
      {...props}
      page={{ items: [shelf], count: 21, next: "/next", previous: null }}
    /></MemoryRouter>);
    expect(markup).toContain('href="/shelves/shelf%2Fid"');
    expect(markup).not.toContain('href="/shelves/shelf%2Fid/edit"');
    expect(markup).toContain('aria-label="Shelves pagination, top"');
    expect(markup).toContain('aria-label="Shelves pagination, bottom"');
    expect(markup.match(/aria-label="Shelves per page"/g)).toHaveLength(1);
    expect(markup).toContain('aria-label="Open Visible Book"');
    expect(markup).toContain("shelf-summary-row-component compact-cover-preview-row");
    expect(markup).toContain("shelf-summary-row-component__identity compact-cover-preview-row__primary");
    expect(markup).not.toContain('aria-label="Delete');
    expect(markup).not.toContain("<form");

    const empty = renderToStaticMarkup(<MemoryRouter><GroupShelvesPageRegion
      {...props}
      page={{ items: [], count: 0, next: null, previous: null }}
    /></MemoryRouter>);
    expect(empty).not.toContain("shelf-summary-row-component");
    expect(empty).toContain('aria-label="Shelves pagination, top"');
    expect(empty).not.toContain('aria-label="Shelves pagination, bottom"');

    const failed = renderToStaticMarkup(<MemoryRouter><GroupShelvesPageRegion
      {...props}
      error={new Error("Shelf discovery failed.")}
    /></MemoryRouter>);
    expect(failed).toContain('role="alert"');
    expect(failed).toMatch(/<button[^>]+type="button"/);
  });
});
