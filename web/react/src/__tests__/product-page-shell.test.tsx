import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ProductPageShellComponent } from "../shared/layout/ProductPageShellComponent";

describe("ProductPageShellComponent", () => {
  it("renders the shared heading contract and page body", () => {
    const markup = renderToStaticMarkup(<ProductPageShellComponent
      eyebrow="Library"
      title="Books"
      description="Visible books"
      actions={<button type="button">New Book</button>}
    ><section>Results</section></ProductPageShellComponent>);

    expect(markup).toContain("<h1>Books</h1>");
    expect(markup).toContain("Library");
    expect(markup).toContain("Visible books");
    expect(markup).toContain("New Book");
    expect(markup).toContain("Results");
  });

  it("supports a frame-only special composition", () => {
    const markup = renderToStaticMarkup(<ProductPageShellComponent><article>Book hero</article></ProductPageShellComponent>);

    expect(markup).toContain("Book hero");
    expect(markup).not.toContain("<h1");
  });
});
