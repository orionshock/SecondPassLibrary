import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ShelfSummaryRowComponent } from "../shared/shelves/ShelfSummaryRowComponent";

describe("ShelfSummaryRowComponent", () => {
  it("renders linked Shelf identity and the required cover preview strip", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      name="Favorites"
      description="Reader picks"
      itemCount={2}
      detailPath="/shelves/shelf%2Fid"
      previewBooks={[{
        id: "book", title: "Preview Book", coverUrl: null, href: "/library/books/book",
      }]}
    /></MemoryRouter>);

    expect(markup).toContain('href="/shelves/shelf%2Fid"');
    expect(markup).toContain("Favorites");
    expect(markup).toContain("Reader picks");
    expect(markup).toContain("(2 books)");
    expect(markup).toContain('aria-label="Book previews"');
    expect(markup).toContain('aria-label="Open Preview Book"');
    expect(markup).not.toContain('aria-label="User:');
    expect(markup).not.toContain('aria-label="Group:');
    expect(markup).not.toContain('aria-label="Public group:');
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Delete");
  });

  it("renders Group and Public identity without mutation affordances", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      name="Common picks"
      description=""
      itemCount={1}
      detailPath="/shelves/public"
      previewBooks={[]}
      owner={{ kind: "group", label: "Common Room", isPublicGroup: true }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="Public group: Common Room"');
    expect(markup).toContain("from");
    expect(markup).toContain("(1 book)");
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Manage");
  });

  it("renders optional user ownership as plain inline identity", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      name="Shared favorites"
      description="A shared shelf"
      itemCount={3}
      detailPath="/shelves/shared"
      previewBooks={[]}
      owner={{ kind: "user", username: "reader" }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="User reader"');
    expect(markup).toContain("reader");
    expect(markup).not.toContain("@reader");
    expect(markup).not.toContain('class="badge');
    expect(markup).toContain("shared by");
    expect(markup).toContain("(3 books)");
    expect(markup).not.toContain('href="/users/');
    expect(markup).not.toContain("Edit");
  });
});
