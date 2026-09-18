/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { BookDetail, CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { BookEditOrchestrator } from "../../../../src/features/library/bookEdit/BookEditOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  getBook: vi.fn(),
  listAuthors: vi.fn(),
  listSeries: vi.fn(),
  listTags: vi.fn(),
  listGroups: vi.fn(),
  listGroupShelves: vi.fn(),
  updateBook: vi.fn(),
  addBookToGroup: vi.fn(),
  removeBookFromGroup: vi.fn(),
  removeShelfItem: vi.fn(),
  replaceCover: vi.fn(),
  clearCover: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getBook: sdk.getBook,
  listAuthors: sdk.listAuthors,
  listSeries: sdk.listSeries,
  listCatalogTags: sdk.listTags,
  listGroups: sdk.listGroups,
  listAllGroupShelvesForBook: sdk.listGroupShelves,
  updateBook: sdk.updateBook,
  addBookToGroup: sdk.addBookToGroup,
  removeBookFromGroup: sdk.removeBookFromGroup,
  removeShelfItem: sdk.removeShelfItem,
  replaceBookCover: sdk.replaceCover,
  clearBookCover: sdk.clearCover,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const book: BookDetail = {
  id: "book/id",
  title: "Original Book",
  sortTitle: "Original Book",
  subtitle: "",
  description: "<p>Original description</p>",
  authors: [{ id: "author-one", name: "Author One" }],
  series: null,
  publisher: "Press",
  language: "eng",
  publishedYear: null,
  publishedMonth: null,
  publishedDay: null,
  publishedDatePrecision: "",
  coverUrl: null,
  catalogTags: [{ id: "tag-one", name: "Fantasy", slug: "fantasy" }],
  identifiers: [],
  file: null,
  groups: [],
};
const authors = [
  { id: "author-one", name: "Author One", sortName: "One, Author", biography: "", bookCount: 1 },
  { id: "author-two", name: "Author Two", sortName: "Two, Author", biography: "", bookCount: 0 },
];
const series = [{ id: "series-one", name: "Series One", sortName: "Series One", summary: "", bookCount: 0 }];
const currentUser = {
  username: "librarian", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "librarian", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: true, isReader: false, canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  installationId: "installation-id",
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev",
  releaseDate: "", publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

function arrangeDependencies() {
  sdk.getBook.mockResolvedValue(book);
  sdk.listAuthors.mockResolvedValue(page(authors));
  sdk.listSeries.mockResolvedValue(page(series));
  sdk.listTags.mockResolvedValue(page([{ id: "tag-one", name: "Fantasy", slug: "fantasy", bookCount: 1 }]));
  sdk.listGroups.mockResolvedValue(page([]));
  sdk.listGroupShelves.mockResolvedValue([]);
}

function page<T>(items: T[]) {
  return { items, count: items.length, next: null, previous: null, catalogTags: [] };
}

async function mount(path = "/library/books/book%2Fid/edit") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [
      { path: "/library/books/:bookId/edit", element: <BookEditOrchestrator /> },
      { path: "/library/books/:bookId", element: <div data-testid="book-detail" /> },
    ],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

async function setRawRichText(container: HTMLElement, id: string, value: string) {
  await act(async () => buttonNamed(container, "Show raw").click());
  await act(async () => setControlValue(container.querySelector<HTMLTextAreaElement>(`textarea#${id}`)!, value));
}

describe("BookEditOrchestrator", () => {
  it("exposes the Book draft without loading any selectable catalog", async () => {
    arrangeDependencies();
    const { container } = await mount();

    expect(sdk.getBook).toHaveBeenCalledWith("book/id");
    expect(sdk.listAuthors).not.toHaveBeenCalled();
    expect(sdk.listSeries).not.toHaveBeenCalled();
    expect(sdk.listTags).not.toHaveBeenCalled();
    expect(sdk.listGroups).not.toHaveBeenCalled();
    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("Original Book");
  });

  it("loads one bounded page only when each choice tab is opened", async () => {
    arrangeDependencies();
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Authors & Series").click());
    expect(sdk.listAuthors).toHaveBeenCalledOnce();
    expect(sdk.listAuthors).toHaveBeenCalledWith({ q: undefined, ordering: "name", pageSize: 25 });
    expect(sdk.listSeries).toHaveBeenCalledOnce();
    expect(sdk.listSeries).toHaveBeenCalledWith({ q: undefined, ordering: "name", pageSize: 25 });

    await act(async () => buttonNamed(container, "Catalog").click());
    expect(sdk.listTags).toHaveBeenCalledOnce();
    expect(sdk.listTags).toHaveBeenCalledWith({ q: undefined, ordering: "name", pageSize: 25 });

    await act(async () => buttonNamed(container, "Library Groups").click());
    expect(sdk.listGroups).toHaveBeenCalledOnce();
    expect(sdk.listGroups).toHaveBeenCalledWith({ q: undefined, ordering: "name", pageSize: 25 });
  });

  it("retains selected relationships when bounded results do not contain them", async () => {
    arrangeDependencies();
    sdk.getBook.mockResolvedValue({
      ...book,
      series: { id: "selected-series", name: "Selected Series", sortName: "Selected Series", seriesIndex: "2.00" },
      groups: [{ id: "selected-group", name: "Selected Group", description: "", isPublicGroup: false }],
    });
    sdk.listAuthors.mockResolvedValue(page([authors[1]]));
    sdk.listSeries.mockResolvedValue(page(series));
    sdk.listTags.mockResolvedValue(page([{ id: "tag-two", name: "Mystery", slug: "mystery", bookCount: 1 }]));
    sdk.listGroups.mockResolvedValue(page([{ id: "other-group", name: "Other Group", description: "", isPublicGroup: false }]));
    const { container } = await mount("/library/books/book%2Fid/edit?tab=authors-series");

    expect(container.textContent).toContain("Author One");
    expect(container.querySelector<HTMLSelectElement>("#book-edit-series")?.value).toBe("selected-series");
    expect(container.querySelector<HTMLInputElement>("#book-edit-series-index")?.value).toBe("2.00");

    await act(async () => buttonNamed(container, "Catalog").click());
    expect(container.textContent).toContain("Fantasy");
    await act(async () => buttonNamed(container, "Library Groups").click());
    expect(container.textContent).toContain("Selected Group");
  });

  it("keeps duplicate Author and Series names distinct by UUID", async () => {
    arrangeDependencies();
    const duplicateAuthors = [
      { ...authors[0], id: "author-alex-1", name: "Alex Smith", sortName: "Smith, Alex" },
      { ...authors[1], id: "author-alex-2", name: "Alex Smith", sortName: "Smith, Alex" },
    ];
    const duplicateSeries = [
      { ...series[0], id: "series-chronicle-1", name: "Chronicle" },
      { ...series[0], id: "series-chronicle-2", name: "Chronicle" },
    ];
    sdk.listAuthors.mockResolvedValue(page(duplicateAuthors));
    sdk.listSeries.mockResolvedValue(page(duplicateSeries));
    const { container } = await mount("/library/books/book%2Fid/edit?tab=authors-series");

    const authorOptions = Array.from(container.querySelectorAll<HTMLOptionElement>("#book-edit-add-author option"));
    expect(authorOptions.map(({ value }) => value)).toEqual(["", "author-alex-1", "author-alex-2"]);
    expect(authorOptions[1]?.textContent).toContain("author-alex-1");
    expect(authorOptions[2]?.textContent).toContain("author-alex-2");
    const seriesOptions = Array.from(container.querySelectorAll<HTMLOptionElement>("#book-edit-series option"));
    expect(seriesOptions.map(({ value }) => value)).toContain("series-chronicle-1");
    expect(seriesOptions.map(({ value }) => value)).toContain("series-chronicle-2");

    await act(async () => setControlValue(
      container.querySelector<HTMLSelectElement>("#book-edit-add-author")!,
      "author-alex-1",
    ));
    await act(async () => buttonNamed(container, "Add author").click());
    await act(async () => setControlValue(
      container.querySelector<HTMLSelectElement>("#book-edit-add-author")!,
      "author-alex-2",
    ));
    await act(async () => buttonNamed(container, "Add author").click());
    sdk.listAuthors.mockResolvedValueOnce(page([]));
    await act(async () => setControlValue(
      container.querySelector<HTMLInputElement>("#book-edit-author-search")!,
      "no match",
    ));
    expect(container.textContent).toContain("author-alex-1");
    expect(container.textContent).toContain("author-alex-2");
  });

  it("ignores an older Author search response after a newer query resolves", async () => {
    arrangeDependencies();
    const older = deferred<ReturnType<typeof page<(typeof authors)[number]>>>();
    const newer = deferred<ReturnType<typeof page<(typeof authors)[number]>>>();
    sdk.listAuthors
      .mockResolvedValueOnce(page(authors))
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise);
    const { container } = await mount("/library/books/book%2Fid/edit?tab=authors-series");
    const search = container.querySelector<HTMLInputElement>("#book-edit-author-search")!;

    await act(async () => setControlValue(search, "mar"));
    await act(async () => setControlValue(search, "mart"));
    await act(async () => newer.resolve(page([{ ...authors[1], id: "newer", name: "Martha" }])));
    expect(container.textContent).toContain("Martha");

    await act(async () => older.resolve(page([{ ...authors[1], id: "older", name: "Marcus" }])));
    expect(container.textContent).toContain("Martha");
    expect(container.textContent).not.toContain("Marcus");

    await act(async () => setControlValue(search, ""));
    expect(sdk.listAuthors).toHaveBeenLastCalledWith({ q: undefined, ordering: "name", pageSize: 25 });
    expect(container.textContent).toContain("Author Two");
  });

  it("isolates Author search failure and retains selected relationships for retry", async () => {
    arrangeDependencies();
    sdk.listAuthors
      .mockRejectedValueOnce(new Error("Author choices unavailable."))
      .mockResolvedValueOnce(page([authors[1]]));
    const { container } = await mount("/library/books/book%2Fid/edit?tab=authors-series");

    expect(container.textContent).toContain("Author One");
    expect(container.textContent).toContain("Author choices unavailable.");
    expect(container.querySelector<HTMLSelectElement>("#book-edit-series")).not.toBeNull();
    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listAuthors).toHaveBeenCalledTimes(2);
    expect(container.textContent).toContain("Author Two");
    expect(container.textContent).toContain("Author One");
  });

  it("retries a failed Book load through the owning SDK request", async () => {
    arrangeDependencies();
    sdk.getBook.mockRejectedValueOnce(new Error("Book load failed."));
    const { container } = await mount();

    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.getBook).toHaveBeenCalledTimes(2);
    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("Original Book");
  });

  it("saves metadata, rich text, Authors, Series, and Catalog Tags as one replacement payload", async () => {
    arrangeDependencies();
    const saved = {
      ...book,
      title: "Edited Book",
      description: "<p>Edited <strong>description</strong></p>",
      authors: [book.authors[0], { id: "author-two", name: "Author Two" }],
      series: { id: "series-one", name: "Series One", sortName: "Series One", seriesIndex: "2.00" },
      catalogTags: [...book.catalogTags, { id: "tag-two", name: "Mystery", slug: "mystery" }],
    } satisfies BookDetail;
    const pendingSave = deferred<BookDetail>();
    sdk.updateBook.mockReturnValue(pendingSave.promise);
    const { container, router } = await mount();

    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#book-edit-title")!, "Edited Book"));
    await setRawRichText(container, "book-edit-description", "<p>Edited <strong>description</strong></p>");
    await act(async () => buttonNamed(container, "Authors & Series").click());
    await act(async () => setControlValue(container.querySelector<HTMLSelectElement>("#book-edit-add-author")!, "author-two"));
    await act(async () => buttonNamed(container, "Add author").click());
    await act(async () => setControlValue(container.querySelector<HTMLSelectElement>("#book-edit-series")!, "series-one"));
    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#book-edit-series-index")!, "2.00"));
    await act(async () => buttonNamed(container, "Catalog").click());
    await act(async () => setControlValue(container.querySelector<HTMLInputElement>('[aria-label="Catalog Tag name"]')!, "Mystery"));
    await act(async () => buttonNamed(container, "Add Catalog Tag").click());

    act(() => submit(container.querySelector("form")!));
    expect(sdk.updateBook).toHaveBeenCalledWith("book/id", expect.objectContaining({
      title: "Edited Book",
      description: "<p>Edited <strong>description</strong></p>",
      authorIds: ["author-one", "author-two"],
      seriesId: "series-one",
      seriesIndex: "2.00",
      catalogTagNames: ["Fantasy", "Mystery"],
    }));
    expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
    const publisherInput = container.querySelector<HTMLInputElement>("#book-edit-publisher")!;
    expect(publisherInput.disabled).toBe(true);
    await act(async () => setControlValue(publisherInput, "Newer Press"));
    expect(publisherInput.value).toBe("Press");
    act(() => submit(container.querySelector("form")!));
    buttonNamed(container, "Saving...").click();
    expect(sdk.updateBook).toHaveBeenCalledOnce();

    await act(async () => pendingSave.resolve(saved));
    expect(container.querySelector("h1")?.textContent).toBe("Edited Book");
    expect(container.querySelector<HTMLInputElement>("#book-edit-publisher")?.disabled).toBe(false);
    const confirm = vi.fn(() => true);
    vi.stubGlobal("confirm", confirm);
    await act(async () => router.navigate("/library/books/book%2Fid"));
    expect(confirm).not.toHaveBeenCalled();
  });

  it("keeps the edited draft recoverable when save fails", async () => {
    arrangeDependencies();
    const failedSave = deferred<BookDetail>();
    sdk.updateBook.mockReturnValueOnce(failedSave.promise).mockResolvedValueOnce({ ...book, title: "Unsaved Book" });
    const { container, router } = await mount();
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);

    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#book-edit-title")!, "Unsaved Book"));
    act(() => submit(container.querySelector("form")!));
    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.disabled).toBe(true);
    await act(async () => router.navigate("/library/books/book%2Fid"));
    expect(router.state.location.pathname).toContain("/edit");
    expect(confirm).not.toHaveBeenCalled();
    await act(async () => failedSave.reject(new Error("Book save failed.")));

    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("Unsaved Book");
    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.disabled).toBe(false);
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
    await act(async () => router.navigate("/library/books/book%2Fid"));
    expect(confirm).toHaveBeenCalledWith("Discard unsaved Book changes?");
    expect(router.state.location.pathname).toContain("/edit");
    await act(async () => submit(container.querySelector("form")!));
    expect(sdk.updateBook).toHaveBeenCalledTimes(2);
  });

  it("ignores a superseded Book load after navigation selects a newer Book", async () => {
    arrangeDependencies();
    const oldLoad = deferred<BookDetail>();
    sdk.getBook.mockImplementation((id: string) => id === "old" ? oldLoad.promise : Promise.resolve({ ...book, id: "new", title: "New Book" }));
    const { container, router } = await mount("/library/books/old/edit");

    await act(async () => router.navigate("/library/books/new/edit"));
    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("New Book");
    await act(async () => oldLoad.resolve({ ...book, id: "old", title: "Old Book" }));

    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("New Book");
  });
});
