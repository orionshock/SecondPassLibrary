import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HelpPopover } from "../components/HelpPopover";

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

  it("renders caller-provided trigger content and border colors", () => {
    const markup = renderToStaticMarkup(<HelpPopover ariaLabel="Trigger description" icon="warning_amber" label="Visible label" mouseoverText="Popover content" border borderColor="#d8b65a" color="#d8b65a" />);
    expect(markup).toContain("warning_amber");
    expect(markup).toContain("Visible label");
    expect(markup).toContain("help-popover__button--bordered");
    expect(markup).toContain("border-color:#d8b65a");
  });
});
