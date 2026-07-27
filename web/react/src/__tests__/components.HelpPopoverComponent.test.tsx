import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { HelpPopoverComponent } from "../components/HelpPopoverComponent";

describe("HelpPopoverComponent", () => {
  it("uses a labelled, described control without a native title", () => {
    const markup = renderToStaticMarkup(<HelpPopoverComponent ariaLabel="Public Group curator help" icon="help" mouseoverText="Only Librarians/Managers may Curate the Public Group" />);

    expect(markup).toContain('type="button"');
    expect(markup).toContain('aria-label="Public Group curator help"');
    expect(markup).toMatch(/aria-describedby="([^"]+)"/);
    expect(markup).toContain('role="tooltip"');
    expect(markup).toContain("Only Librarians/Managers may Curate the Public Group");
    expect(markup).not.toContain("title=");
  });

  it("supports a warning triangle without changing the default help treatment", () => {
    const warning = renderToStaticMarkup(<HelpPopoverComponent ariaLabel="Import warning" icon="warning_amber" label="Unmatched" mouseoverText="This Book is unmatched." border borderColor="#d8b65a" color="#d8b65a" />);
    expect(warning).toContain("warning_amber");
    expect(warning).toContain("Unmatched");
    expect(warning).toContain("help-popover__button--bordered");
    expect(warning).toContain("border-color:#d8b65a");
    expect(renderToStaticMarkup(<HelpPopoverComponent ariaLabel="Help" icon="help" mouseoverText="Details" />)).toContain(">help</span>");
  });
});
