import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ReadingSectionActionsComponent, type ReadingSection } from "../features/reading/components/ReadingSectionActionsComponent";

const destinations: Record<ReadingSection, string> = {
  sessions: "/reading",
  import: "/reading/import",
  export: "/reading/export",
};

describe("ReadingSectionActionsComponent", () => {
  it.each(Object.entries(destinations) as Array<[ReadingSection, string]>)
  ("renders all section routes and marks %s as the current page", (activeSection, activePath) => {
    const markup = renderToStaticMarkup(<MemoryRouter><ReadingSectionActionsComponent activeSection={activeSection} /></MemoryRouter>);

    expect(markup).toContain('aria-label="My Marginalia sections"');
    expect(markup).toContain('href="/reading"');
    expect(markup).toContain('href="/reading/import"');
    expect(markup).toContain('href="/reading/export"');
    expect(markup).toMatch(new RegExp(`<a(?=[^>]*aria-current="page")(?=[^>]*href="${activePath}")[^>]*>`));
    expect(markup.match(/aria-current="page"/g)).toHaveLength(1);
    expect(markup).not.toContain('role="tablist"');
  });
});
