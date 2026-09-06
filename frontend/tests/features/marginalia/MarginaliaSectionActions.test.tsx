import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";

import { MarginaliaSectionActions, type MarginaliaSection } from "../../../src/features/marginalia/components/MarginaliaSectionActions";

const destinations: Record<MarginaliaSection, string> = {
  sessions: "/marginalia",
  import: "/marginalia/import",
  export: "/marginalia/export",
};

describe("MarginaliaSectionActions", () => {
  it.each(Object.entries(destinations) as Array<[MarginaliaSection, string]>)
  ("renders all section routes and marks %s as the current page", (activeSection, activePath) => {
    const markup = renderToStaticMarkup(<MemoryRouter><MarginaliaSectionActions activeSection={activeSection} /></MemoryRouter>);

    expect(markup).toContain('aria-label="My Marginalia sections"');
    expect(markup).toContain('href="/marginalia"');
    expect(markup).toContain('href="/marginalia/import"');
    expect(markup).toContain('href="/marginalia/export"');
    expect(markup).toMatch(new RegExp(`<a(?=[^>]*aria-current="page")(?=[^>]*href="${activePath}")[^>]*>`));
    expect(markup.match(/aria-current="page"/g)).toHaveLength(1);
    expect(markup).not.toContain('role="tablist"');
  });
});
