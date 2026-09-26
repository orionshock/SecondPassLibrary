/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthorSeriesEditFormPageRegion } from "../../../src/features/library/authorSeriesEdit/AuthorSeriesEditFormPageRegion";
import { BookEditBookPageRegion } from "../../../src/features/library/bookEdit/BookEditBookPageRegion";
import type { BookEditDraft } from "../../../src/features/library/bookEdit/bookEditDraft";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean })
  .IS_REACT_ACT_ENVIRONMENT = true;

let container: HTMLDivElement | undefined;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  container?.remove();
  root = undefined;
  container = undefined;
});

const bookDraft: BookEditDraft = {
  title: "Book",
  sortTitle: "",
  subtitle: "",
  description: "<p>Rich <strong>description</strong></p>",
  publisher: "",
  language: "",
  publishedDatePrecision: "",
  publishedYear: "",
  publishedMonth: "",
  publishedDay: "",
  catalogTagNames: [],
  authorIds: [],
  seriesId: null,
  seriesIndex: "",
  identifiers: [],
};

describe("Library descriptive metadata editing", () => {
  it("wires Book, Author, and Series prose to the bounded editor", async () => {
    container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);

    await act(async () => root?.render(<BookEditBookPageRegion
      draft={bookDraft}
      onChange={vi.fn()}
    />));

    const editor = container.querySelector<HTMLElement>("#book-edit-description");
    expect(editor?.getAttribute("contenteditable")).toBe("true");
    expect(container.querySelector(".limited-rich-text-editor__count")?.textContent)
      .toContain("/ 25,000");

    const common = {
      state: { pending: false },
      advisory: {
        enabled: false,
        candidates: [],
        pending: false,
        onSelectCandidate: vi.fn(),
      },
      onChange: vi.fn(),
      onSubmit: vi.fn(),
      onCancel: vi.fn(),
    };

    await act(async () => root?.render(<AuthorSeriesEditFormPageRegion
      {...common}
      kind="author"
      draft={{ name: "Author", sortName: "", prose: "<p>Rich <strong>biography</strong></p>" }}
    />));
    expect(container.querySelector<HTMLElement>("#library-entity-prose")?.getAttribute("contenteditable"))
      .toBe("true");
    expect(container.querySelector(".limited-rich-text-editor__count")?.textContent)
      .toContain("/ 25,000");

    await act(async () => root?.render(<AuthorSeriesEditFormPageRegion
      {...common}
      kind="series"
      draft={{ name: "Series", sortName: "", prose: "<ul><li><em>Summary</em></li></ul>" }}
    />));
    expect(container.querySelector<HTMLElement>("#library-entity-prose")?.getAttribute("contenteditable"))
      .toBe("true");
  });
});
