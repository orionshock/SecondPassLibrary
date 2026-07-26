import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ShelfSummaryRowComponent } from "../shared/shelves/ShelfSummaryRowComponent";

describe("ShelfSummaryRowComponent", () => {
  it("renders linked read-only Shelf identity and facts", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      shelf={{
        name: "Favorites",
        description: "Reader picks",
        ownerType: "user",
        ownerUser: { username: "reader" },
        ownerGroup: null,
        visibility: "listed",
        itemCount: 2,
        canEdit: false,
      }}
      detailPath="/shelves/shelf%2Fid"
    /></MemoryRouter>);

    expect(markup).toContain('href="/shelves/shelf%2Fid"');
    expect(markup).toContain("Favorites");
    expect(markup).toContain("Reader picks");
    expect(markup).toContain("Shared by @reader");
    expect(markup).toContain("Listed");
    expect(markup).toContain("2 items");
    expect(markup).not.toContain("Edit");
    expect(markup).not.toContain("Delete");
  });

  it("renders Group and Public identity without user visibility facts", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><ShelfSummaryRowComponent
      shelf={{
        name: "Common picks",
        description: "",
        ownerType: "group",
        ownerUser: null,
        ownerGroup: { name: "Common Room", isPublicGroup: true },
        visibility: "private",
        itemCount: 1,
        canEdit: true,
      }}
      detailPath="/shelves/public"
    /></MemoryRouter>);

    expect(markup).toContain('aria-label="Public group: Common Room"');
    expect(markup).toContain("1 item");
    expect(markup).not.toContain("Private");
  });
});
