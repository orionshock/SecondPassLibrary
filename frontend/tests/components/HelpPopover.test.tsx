import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HelpPopover } from "../../src/components/HelpPopover";

describe("HelpPopover", () => {
  it("uses a labelled, described control without a native title", () => {
    const markup = renderToStaticMarkup(<HelpPopover ariaLabel="Trigger description" icon="help" mouseoverText="Popover content" />);

    expect(markup).toContain('type="button"');
    expect(markup).toContain('aria-label="Trigger description"');
    expect(markup).toMatch(/aria-describedby="([^"]+)"/);
    expect(markup).toContain('role="tooltip"');
    expect(markup).toContain("Popover content");
    expect(markup).not.toContain("title=");
  });
});

