import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { PaginatedListFrame } from "../shared/pagination/PaginatedListFrame";
import { Pager } from "../shared/pagination/Pager";

const callbacks = {
  onPageChange: vi.fn(),
  onPageSizeChange: vi.fn(),
};

describe("shared pagination", () => {
  it("keeps the page-size selector in full mode and omits it in compact mode", () => {
    const props = {
      page: 2,
      pageSize: 20,
      count: 45,
      hasPrevious: true,
      hasNext: true,
      itemLabel: "Books",
      ...callbacks,
    };
    const full = renderToStaticMarkup(<Pager {...props} ariaLabel="Full books pager" />);
    const compact = renderToStaticMarkup(<Pager {...props} density="compact" ariaLabel="Compact books pager" />);

    expect(full).toContain('aria-label="Full books pager"');
    expect(full).toContain('aria-label="Books per page"');
    expect(compact).toContain('aria-label="Compact books pager"');
    expect(compact).not.toContain('aria-label="Books per page"');
    expect(compact).toContain("Showing 21-40 of 45");
    expect(compact).toContain("Previous");
    expect(compact).toContain("Next");
  });

  it("frames children with a compact top pager and full bottom pager", () => {
    const markup = renderToStaticMarkup(<PaginatedListFrame
      page={1}
      pageSize={20}
      count={21}
      hasPrevious={false}
      hasNext
      itemLabel="Users"
      pageSizes={[20, 50, 100, 200]}
      topControls={<div data-top-control="true">Order control</div>}
      {...callbacks}
    >
      <div data-list-body="true">Rows</div>
    </PaginatedListFrame>);

    const top = markup.indexOf('aria-label="Users pagination, top"');
    const topControl = markup.indexOf('data-top-control="true"');
    const body = markup.indexOf('data-list-body="true"');
    const bottom = markup.indexOf('aria-label="Users pagination, bottom"');
    expect(top).toBeGreaterThanOrEqual(0);
    expect(topControl).toBeGreaterThan(top);
    expect(topControl).toBeLessThan(body);
    expect(body).toBeGreaterThan(top);
    expect(bottom).toBeGreaterThan(body);
    expect(markup).toContain('<option value="200">200</option>');
    expect(markup.match(/aria-label="Users per page"/g)).toHaveLength(1);
  });

  it("omits the full bottom pager for an empty result", () => {
    const markup = renderToStaticMarkup(<PaginatedListFrame
      page={1}
      pageSize={20}
      count={0}
      hasPrevious={false}
      hasNext={false}
      itemLabel="Shelves"
      {...callbacks}
    >
      <p>No shelves.</p>
    </PaginatedListFrame>);

    expect(markup).toContain('aria-label="Shelves pagination, top"');
    expect(markup).not.toContain('aria-label="Shelves pagination, bottom"');
  });
});
