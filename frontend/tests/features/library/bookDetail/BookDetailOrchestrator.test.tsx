/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError, type BookDetail, type CurrentUser, type LibraryGroup, type ServerInfo, type ShelfSummary } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { BookDetailOrchestrator } from "../../../../src/features/library/bookDetail/BookDetailOrchestrator";
import { buttonNamed, deferred } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ getBook: vi.fn(), listShelves: vi.fn(), listGroups: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getBook: sdk.getBook,
  listAllShelvesForBook: sdk.listShelves,
  listAllGroupsForBook: sdk.listGroups,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const book = (id: string, title: string): BookDetail => ({
  id, title, sortTitle: title, subtitle: "", authors: [{ id: "author", name: "Author" }],
  series: { id: "series", name: "Series", sortName: "Series", seriesIndex: "1.00" },
  language: "eng", publisher: "Publisher", publishedYear: 2026, publishedMonth: null, publishedDay: null,
  publishedDatePrecision: "year", coverUrl: null, description: "<p>Description</p>", identifiers: [],
  catalogTags: [{ id: "tag", name: "Tag", slug: "tag" }],
  file: { format: "epub", fileSize: 10, checksum: "checksum", downloadUrl: "/download/book.epub" }, groups: [],
});
const shelf: ShelfSummary = {
  id: "shelf", name: "Containing Shelf", description: "", ownerType: "user",
  ownerUser: { profileId: "reader", username: "reader" }, ownerGroup: null, visibility: "private",
  itemCount: 1, previewBooks: [], canEdit: true,
};
const group: LibraryGroup = { id: "group", name: "Containing Group", description: "", isPublicGroup: false, previewBooks: [] };
const librarian = {
  username: "librarian", email: "", firstName: "", lastName: "", profileId: "librarian", role: "librarian",
  mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: true, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  serverId: "server-id", serverUrls: [],
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: "https://reader.example.com", marginaliaProfileUri: "profile", version: "dev", releaseDate: "",
  publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function prime() {
  sdk.getBook.mockResolvedValue(book("book-one", "Book One"));
  sdk.listShelves.mockResolvedValue([shelf]);
  sdk.listGroups.mockResolvedValue([group]);
}

async function mount(path = "/library/books/book-one", currentUser: CurrentUser = librarian, info: ServerInfo = serverInfo) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = { currentUser, serverInfo: info, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  const router = createMemoryRouter([{ element: <Outlet context={context} />, children: [{ path: "/library/books/:bookId", element: <BookDetailOrchestrator /> }] }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("BookDetailOrchestrator", () => {
  it("loads Book identity and exposes configured Reader and authorized edit destinations", async () => {
    prime();
    const { container } = await mount();

    expect(sdk.getBook).toHaveBeenCalledWith("book-one");
    expect(container.querySelector('a[href="https://reader.example.com/#/reader/book-one"]')).toMatchObject({ target: "_blank" });
    expect(container.querySelector('a[href="/library/books/book-one/edit"]')).not.toBeNull();
    expect(container.querySelector('a[href*="author=author"]')).not.toBeNull();
    expect(container.querySelector('a[href*="series=series"]')).not.toBeNull();
  });

  it("suppresses Reader launch without a configured origin and edit navigation without authority", async () => {
    prime();
    const reader = { ...librarian, role: "reader", isLibrarian: false, isReader: true } satisfies CurrentUser;
    const { container } = await mount("/library/books/book-one", reader, { ...serverInfo, secondPassReaderWebClientUrl: null });

    expect(container.querySelector('a[target="_blank"]')).toBeNull();
    expect(container.querySelector('a[href="/library/books/book-one/edit"]')).toBeNull();
  });

  it("retries a failed Book load and distinguishes an unavailable Book", async () => {
    sdk.getBook.mockRejectedValueOnce(new Error("Book unavailable.")).mockResolvedValueOnce(book("book-one", "Recovered Book"));
    sdk.listShelves.mockResolvedValue([]);
    const { container, router } = await mount();

    await act(async () => buttonNamed(container, "Retry").click());
    expect(container.textContent).toContain("Recovered Book");

    sdk.getBook.mockRejectedValueOnce(new ApiError("Missing.", 404));
    await act(async () => router.navigate("/library/books/missing"));
    expect(container.textContent).toContain("Book not found");
  });

  it("loads relationship sections lazily and retries a failed section", async () => {
    sdk.getBook.mockResolvedValue(book("book-one", "Book One"));
    sdk.listShelves.mockRejectedValueOnce(new Error("Shelves unavailable.")).mockResolvedValueOnce([shelf]);
    sdk.listGroups.mockResolvedValue([group]);
    const { container } = await mount();

    expect(sdk.listShelves).toHaveBeenCalledWith("book-one", 12);
    expect(sdk.listGroups).not.toHaveBeenCalled();
    await act(async () => buttonNamed(container, "Retry").click());
    expect(container.querySelector('a[href="/shelves/shelf"]')).not.toBeNull();

    await act(async () => buttonNamed(container, "Groups").click());
    expect(sdk.listGroups).toHaveBeenCalledWith("book-one", 12);
    expect(container.querySelector('a[href="/groups/group"]')).not.toBeNull();
  });

  it("does not let the previous route identity replace the current Book or its relationships", async () => {
    const oldBook = deferred<BookDetail>();
    const newBook = deferred<BookDetail>();
    sdk.getBook.mockReturnValueOnce(oldBook.promise).mockReturnValueOnce(newBook.promise);
    sdk.listShelves.mockResolvedValue([]);
    const { container, router } = await mount();

    await act(async () => router.navigate("/library/books/book-two"));
    expect(sdk.getBook).toHaveBeenLastCalledWith("book-two");
    await act(async () => newBook.resolve(book("book-two", "Book Two")));
    await act(async () => oldBook.resolve(book("book-one", "Book One")));

    expect(container.textContent).toContain("Book Two");
    expect(container.textContent).not.toContain("Book One");
    expect(sdk.listShelves).toHaveBeenCalledWith("book-two", 12);
  });
});
