import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { OrderSelectComponent } from "../shared/forms/OrderSelectComponent";

describe("OrderSelectComponent", () => {
  it("renders an accessible native select with an inline label and selected icon", () => {
    const markup = renderToStaticMarkup(<OrderSelectComponent
      aria-label="Order groups"
      value="-name"
      options={[
        { value: "name", label: "Name A-Z", icon: "sort_by_alpha" },
        { value: "-name", label: "Name Z-A", icon: "sort_by_alpha" },
      ] as const}
      onChange={vi.fn()}
    />);

    expect(markup).toContain(">Order</span>");
    expect(markup).toContain('aria-label="Order groups"');
    expect(markup).toContain("sort_by_alpha");
    expect(markup).toContain('<option value="-name" selected="">Name Z-A</option>');
  });
});
