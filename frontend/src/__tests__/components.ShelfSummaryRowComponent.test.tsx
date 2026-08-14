import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { ShelfSummaryRow } from "../shared/shelves/ShelfSummaryRow";

describe("ShelfSummaryRow", () => {
  it("renders linked Shelf identity and the required cover preview strip", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRow
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
    expect(markup).toContain("2 books");
    expect(markup.match(/class="css-dot"/g)).toHaveLength(1);
    expect(markup).toContain('aria-label="Book previews"');
    expect(markup).toContain('aria-label="Open Preview Book"');
    expect(markup).toContain("shelf-summary-row-component compact-cover-preview-row");
    expect(markup).toContain("shelf-summary-row-component__identity compact-cover-preview-row__primary");
    expect(markup).not.toContain('aria-label="User:');
    expect(markup).not.toContain('aria-label="Group:');
    expect(markup).not.toContain('aria-label="Public group:');
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Delete");
  });

  it("renders Group and Public identity without mutation affordances", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRow
      name="Common picks"
      description=""
      itemCount={1}
      detailPath="/shelves/public"
      previewBooks={[]}
      owner={{ kind: "group", label: "Common Room", isPublicGroup: true }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="Public group: Common Room"');
    expect(markup).toMatch(/shelf-summary-row-component__source[^>]*>.*Public group: Common Room/);
    expect(markup).toContain("from");
    expect(markup).toContain("1 book");
    expect(markup.match(/class="css-dot"/g)).toHaveLength(2);
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Manage");
  });

  it("renders optional user ownership as plain inline identity", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRow
      name="Shared favorites"
      description="A shared shelf"
      itemCount={3}
      detailPath="/shelves/shared"
      previewBooks={[]}
      owner={{ kind: "user", username: "reader" }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="User reader"');
    expect(markup).toMatch(/shelf-summary-row-component__source[^>]*>.*User reader/);
    expect(markup).toContain("reader");
    expect(markup).not.toContain("@reader");
    expect(markup).not.toContain('class="badge');
    expect(markup).toContain("shared by");
    expect(markup).toContain("3 books");
    expect(markup.match(/class="css-dot"/g)).toHaveLength(2);
    expect(markup).not.toContain('href="/users/');
    expect(markup).not.toContain("Edit");
  });
});
