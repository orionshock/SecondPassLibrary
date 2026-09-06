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
  listAllAuthors: sdk.listAuthors,
  listAllSeries: sdk.listSeries,
  listAllCatalogTags: sdk.listTags,
  listAllLibraryGroups: sdk.listGroups,
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
  sdk.listAuthors.mockResolvedValue(authors);
  sdk.listSeries.mockResolvedValue(series);
  sdk.listTags.mockResolvedValue([{ id: "tag-one", name: "Fantasy", slug: "fantasy", count: 1 }]);
  sdk.listGroups.mockResolvedValue([]);
  sdk.listGroupShelves.mockResolvedValue([]);
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
  it("loads the Book and every required picker before exposing the draft", async () => {
    arrangeDependencies();
    const { container } = await mount();

    expect(sdk.getBook).toHaveBeenCalledWith("book/id");
    expect(sdk.listAuthors).toHaveBeenCalledOnce();
    expect(sdk.listSeries).toHaveBeenCalledOnce();
    expect(sdk.listTags).toHaveBeenCalledOnce();
    expect(sdk.listGroups).toHaveBeenCalledOnce();
    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("Original Book");
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
    const { container } = await mount();

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
    buttonNamed(container, "Saving...").click();
    expect(sdk.updateBook).toHaveBeenCalledOnce();

    await act(async () => pendingSave.resolve(saved));
    expect(container.querySelector("h1")?.textContent).toBe("Edited Book");
  });

  it("keeps the edited draft recoverable when save fails", async () => {
    arrangeDependencies();
    sdk.updateBook.mockRejectedValue(new Error("Book save failed."));
    const { container } = await mount();

    await act(async () => setControlValue(container.querySelector<HTMLInputElement>("#book-edit-title")!, "Unsaved Book"));
    await act(async () => submit(container.querySelector("form")!));

    expect(container.querySelector<HTMLInputElement>("#book-edit-title")?.value).toBe("Unsaved Book");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
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
