import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { CompactBook, LibraryGroup } from "@second-pass/spl-api";
import { GroupMemberRowComponent } from "../features/groups/components/GroupMemberRowComponent";
import { GroupRowComponent } from "../features/groups/components/GroupRowComponent";
import { GroupBooksPageRegion } from "../features/groups/regions/GroupBooksPageRegion";
import { GroupHeaderPageRegion } from "../features/groups/regions/GroupHeaderPageRegion";
import { GroupMembersPageRegion } from "../features/groups/regions/GroupMembersPageRegion";
import { GroupsListPageRegion } from "../features/groups/regions/GroupsListPageRegion";

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
    const markup = renderToStaticMarkup(<MemoryRouter><GroupRowComponent
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

  it("renders only Books and Members detail sections", () => {
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
    expect(markup).not.toContain("Shelves");
    expect(markup).not.toContain("href=");
  });

  it("renders the Manage destination only when authorized by its orchestrator", () => {
    const detail = renderToStaticMarkup(<MemoryRouter><GroupHeaderPageRegion
      group={{ ...group, isPublicGroup: false }}
      loading={false}
      isCurator={false}
      editPath="/groups/group/edit"
      activeTab="books"
      onTabChange={vi.fn()}
      onRetry={vi.fn()}
    /></MemoryRouter>);
    expect(detail).toContain('href="/groups/group/edit"');
    expect(detail).toContain(">Manage</a>");

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
    expect(markup).not.toContain("Remove book");
    expect(markup).not.toContain("Add book");
  });

  it("renders username and curator state without membership internals", () => {
    const membership = { user: { profileId: "profile", username: "reader" }, isCurator: true };
    const row = renderToStaticMarkup(<GroupMemberRowComponent membership={membership} />);
    expect(row).toContain("&lt;@reader&gt;");
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
});
