import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";

import { PaginatedListFrame } from "../../../src/shared/pagination/PaginatedListFrame";
import { Pager } from "../../../src/shared/pagination/Pager";

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

  it("exposes distinct navigation landmarks and one page-size control", () => {
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

    expect(markup).toContain('aria-label="Users pagination, top"');
    expect(markup).toContain('aria-label="Users pagination, bottom"');
    expect(markup).toContain('data-top-control="true"');
    expect(markup).toContain('data-list-body="true"');
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

