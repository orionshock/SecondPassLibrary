import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { MarginaliaSectionActionsComponent, type MarginaliaSection } from "../features/marginalia/components/MarginaliaSectionActionsComponent";

const destinations: Record<MarginaliaSection, string> = {
  sessions: "/marginalia",
  import: "/marginalia/import",
  export: "/marginalia/export",
};

describe("MarginaliaSectionActionsComponent", () => {
  it.each(Object.entries(destinations) as Array<[MarginaliaSection, string]>)
  ("renders all section routes and marks %s as the current page", (activeSection, activePath) => {
    const markup = renderToStaticMarkup(<MemoryRouter><MarginaliaSectionActionsComponent activeSection={activeSection} /></MemoryRouter>);

    expect(markup).toContain('aria-label="My Marginalia sections"');
    expect(markup).toContain('href="/marginalia"');
    expect(markup).toContain('href="/marginalia/import"');
    expect(markup).toContain('href="/marginalia/export"');
    expect(markup).toContain(">history</span><span>My Marginalia</span>");
    expect(markup).toContain(">upload_file</span><span>Import</span>");
    expect(markup).toContain(">download</span><span>Export</span>");
    expect(markup.match(/aria-hidden="true"/g)).toHaveLength(3);
    expect(markup).toMatch(new RegExp(`<a(?=[^>]*aria-current="page")(?=[^>]*href="${activePath}")[^>]*>`));
    expect(markup.match(/aria-current="page"/g)).toHaveLength(1);
    expect(markup).not.toContain('role="tablist"');
  });
});
