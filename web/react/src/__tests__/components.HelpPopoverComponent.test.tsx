import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HelpPopoverComponent } from "../components/HelpPopoverComponent";

describe("HelpPopoverComponent", () => {
  it("uses a labelled, described control without a native title", () => {
    const markup = renderToStaticMarkup(<HelpPopoverComponent label="Public Group curator help">Only Librarians/Managers may Curate the Public Group</HelpPopoverComponent>);

    expect(markup).toContain('type="button"');
    expect(markup).toContain('aria-label="Public Group curator help"');
    expect(markup).toMatch(/aria-describedby="([^"]+)"/);
    expect(markup).toContain('role="tooltip"');
    expect(markup).toContain("Only Librarians/Managers may Curate the Public Group");
    expect(markup).not.toContain("title=");
  });
});
