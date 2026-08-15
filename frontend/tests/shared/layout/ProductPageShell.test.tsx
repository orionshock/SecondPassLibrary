import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { ProductPageShell } from "../../../src/shared/layout/ProductPageShell";

describe("ProductPageShell", () => {
  it("renders the shared heading contract and page body", () => {
    const markup = renderToStaticMarkup(<ProductPageShell
      eyebrow="Library"
      title="Books"
      description="Visible books"
      actions={<button type="button">New Book</button>}
    ><section>Results</section></ProductPageShell>);

    expect(markup).toContain("<h1>Books</h1>");
    expect(markup).toContain("Library");
    expect(markup).toContain("Visible books");
    expect(markup).toContain("New Book");
    expect(markup).toContain("Results");
  });

  it("supports a frame-only special composition", () => {
    const markup = renderToStaticMarkup(<ProductPageShell><article>Book hero</article></ProductPageShell>);

    expect(markup).toContain("Book hero");
    expect(markup).not.toContain("<h1");
  });
});

