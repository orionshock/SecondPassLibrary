import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ShelfSummaryRowComponent } from "../shared/shelves/ShelfSummaryRowComponent";

describe("ShelfSummaryRowComponent", () => {
  it("renders linked Shelf identity and the required cover preview strip", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      name="Favorites"
      description="Reader picks"
      detailPath="/shelves/shelf%2Fid"
      previewBooks={[{
        id: "book", title: "Preview Book", coverUrl: null, href: "/library/books/book",
      }]}
    /></MemoryRouter>);

    expect(markup).toContain('href="/shelves/shelf%2Fid"');
    expect(markup).toContain("Favorites");
    expect(markup).toContain("Reader picks");
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
      detailPath="/shelves/public"
      previewBooks={[]}
      owner={{ kind: "group", label: "Common Room", isPublicGroup: true }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="Public group: Common Room"');
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Manage");
  });

  it("renders an optional display-only user owner pill", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      name="Shared favorites"
      description="A shared shelf"
      detailPath="/shelves/shared"
      previewBooks={[]}
      owner={{ kind: "user", label: "@reader" }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="User: @reader"');
    expect(markup).toContain("@reader");
    expect(markup).not.toContain('href="/users/');
    expect(markup).not.toContain("Edit");
  });
});
