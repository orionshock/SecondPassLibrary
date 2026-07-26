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
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Delete");
  });

  it("renders Group and Public identity without user visibility facts", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      name="Common picks"
      description=""
      detailPath="/shelves/public"
      previewBooks={[]}
      group={{ name: "Common Room", isPublicGroup: true }}
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="Public group: Common Room"');
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Manage");
  });
});
