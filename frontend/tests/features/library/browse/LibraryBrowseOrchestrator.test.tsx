/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CatalogResultPage, CatalogTag, CompactBook, CurrentUser, LibraryAuthor, LibrarySeries, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { LibraryOrchestrator } from "../../../../src/features/library/browse/LibraryOrchestrator";
import { buttonNamed, deferred } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  listBooks: vi.fn(), listAuthors: vi.fn(), listSeries: vi.fn(), listTags: vi.fn(), getAuthor: vi.fn(), getSeries: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listBooks: sdk.listBooks,
  listAuthors: sdk.listAuthors,
  listSeries: sdk.listSeries,
  listAllCatalogTags: sdk.listTags,
  getAuthor: sdk.getAuthor,
  getSeries: sdk.getSeries,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const fantasy: CatalogTag = { id: "fantasy", name: "Fantasy", slug: "fantasy", bookCount: 4 };
const compactBook = (id: string, title: string): CompactBook => ({
  id, title, sortTitle: title, subtitle: "", authors: [], series: null, catalogTags: [], language: "",
  publisher: "", publishedYear: null, publishedMonth: null, publishedDay: null,
  publishedDatePrecision: "", coverUrl: null, fileFormat: "epub",
});
const catalogPage = <T,>(items: T[], catalogTags: CatalogTag[] = [fantasy]): CatalogResultPage<T> => ({
  items, count: items.length, next: null, previous: null, catalogTags,
});
const currentUser = {
  username: "librarian", email: "", firstName: "", lastName: "", profileId: "profile", role: "librarian",
  mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: true, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: false,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev", releaseDate: "",
  publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount(path = "/library") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/library", element: <LibraryOrchestrator /> }],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

function primeCatalog() {
  sdk.listTags.mockResolvedValue([fantasy]);
  sdk.listBooks.mockResolvedValue(catalogPage([compactBook("book-one", "Book One")]));
  sdk.listAuthors.mockResolvedValue(catalogPage<LibraryAuthor>([]));
  sdk.listSeries.mockResolvedValue(catalogPage<LibrarySeries>([]));
}

describe("LibraryOrchestrator browse behavior", () => {
  it("loads URL-backed Book search, pagination, and selected Catalog Tag metadata", async () => {
    primeCatalog();
    const { container } = await mount("/library?q=history&tag=fantasy&page=2&page_size=30");

    expect(sdk.listTags).toHaveBeenCalledOnce();
    expect(sdk.listBooks).toHaveBeenCalledWith({ q: "history", tag: "fantasy", ordering: "title", page: 2, pageSize: 30 });
    expect(container.querySelector('a[href="/library/books/book-one"]')).not.toBeNull();
    const activeTag = Array.from(container.querySelectorAll<HTMLButtonElement>('aside[aria-label="Catalog Tags"] button'))
      .find((button) => button.getAttribute("aria-pressed") === "true" && button.textContent?.includes("Fantasy"));
    expect(activeTag).toBeDefined();
  });

  it("switches axes and delegates the Author result request to the axis SDK", async () => {
    primeCatalog();
    sdk.listAuthors.mockResolvedValue(catalogPage([{ id: "author", name: "Author Result", sortName: "Result, Author", biography: "", bookCount: 1 }]));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Authors").click());

    expect(sdk.listAuthors).toHaveBeenCalledWith(expect.objectContaining({ ordering: "name", includePreviewBooks: true, page: 1, pageSize: 20 }));
    expect(container.querySelector('a[href*="author=author"]')).not.toBeNull();
  });

  it("retries a failed Book request without reloading the already available tag scope", async () => {
    sdk.listTags.mockResolvedValue([fantasy]);
    sdk.listBooks.mockRejectedValueOnce(new Error("Books unavailable.")).mockResolvedValueOnce(catalogPage([compactBook("recovered", "Recovered Book")]));
    const { container } = await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listBooks).toHaveBeenCalledTimes(2);
    expect(sdk.listTags).toHaveBeenCalledOnce();
    expect(container.querySelector('a[href="/library/books/recovered"]')).not.toBeNull();
  });

  it("does not allow an older Book query to replace newer Library results", async () => {
    sdk.listTags.mockResolvedValue([fantasy]);
    const oldRequest = deferred<CatalogResultPage<CompactBook>>();
    const newRequest = deferred<CatalogResultPage<CompactBook>>();
    sdk.listBooks.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    const { container, router } = await mount("/library?q=old");

    await act(async () => router.navigate("/library?q=new"));
    await act(async () => newRequest.resolve(catalogPage([compactBook("new", "New Book")])));
    await act(async () => oldRequest.resolve(catalogPage([compactBook("old", "Old Book")])));

    expect(container.querySelector('a[href="/library/books/new"]')).not.toBeNull();
    expect(container.querySelector('a[href="/library/books/old"]')).toBeNull();
  });
});
