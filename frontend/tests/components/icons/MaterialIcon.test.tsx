import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { MaterialIcon } from "../../../src/components/icons/MaterialIcon";

describe("MaterialIcon", () => {
  it("hides decorative icons from assistive technology", () => {
    const markup = renderToStaticMarkup(<MaterialIcon name="check" />);

    expect(markup).toContain('aria-hidden="true"');
    expect(markup).toContain(">check</span>");
  });

  it("labels meaningful icons", () => {
    const markup = renderToStaticMarkup(
      <MaterialIcon name="person" label="Profile" title="Open profile" size={18} />,
    );

    expect(markup).toContain('role="img"');
    expect(markup).toContain('aria-label="Profile"');
    expect(markup).toContain('title="Open profile"');
    expect(markup).not.toContain("aria-hidden");
  });
});

