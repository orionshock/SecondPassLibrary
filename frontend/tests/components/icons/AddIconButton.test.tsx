import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { AddIconButton } from "../../../src/components/icons/AddIconButton";

describe("AddIconButton", () => {
  it("owns the standard add icon treatment and accessible label", () => {
    const markup = renderToStaticMarkup(<AddIconButton label="Add author" />);

    expect(markup).toContain('aria-label="Add author"');
    expect(markup).toContain(">add</span>");
  });
});

