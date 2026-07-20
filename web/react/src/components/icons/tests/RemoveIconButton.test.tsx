import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { RemoveIconButton } from "../RemoveIconButton";

describe("RemoveIconButton", () => {
  it("owns the standard destructive icon treatment and accessible label", () => {
    const markup = renderToStaticMarkup(<RemoveIconButton label="Remove reader" />);

    expect(markup).toContain("icon-button--danger");
    expect(markup).toContain('aria-label="Remove reader"');
    expect(markup).toContain("remove_circle");
  });
});
