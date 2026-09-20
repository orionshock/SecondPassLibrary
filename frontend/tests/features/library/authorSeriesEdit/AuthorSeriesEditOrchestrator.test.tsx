/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, LibraryAuthor, LibrarySeries, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { AuthorSeriesEditOrchestrator } from "../../../../src/features/library/authorSeriesEdit/AuthorSeriesEditOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  getAuthor: vi.fn(), getSeries: vi.fn(), listBooks: vi.fn(), listAuthors: vi.fn(), listSeries: vi.fn(),
  createAuthor: vi.fn(), createSeries: vi.fn(), updateAuthor: vi.fn(), updateSeries: vi.fn(),
  deleteAuthor: vi.fn(), deleteSeries: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  ...sdk,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const author: LibraryAuthor = {
  id: "author/id", name: "Ada Author", sortName: "Author, Ada",
  biography: "<p>Original biography</p>", bookCount: 0,
};
const series: LibrarySeries = {
  id: "series/id", name: "Example Series", sortName: "Example Series",
  summary: "<p>Original summary</p>", bookCount: 0,
};
const currentUser = {
  username: "librarian", email: "", firstName: "", lastName: "", profileId: "profile",
  role: "librarian", mustChangePassword: false, isOwner: false, isManager: false,
  isLibrarian: true, isReader: false, canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  serverId: "server-id", serverUrls: [],
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev",
  releaseDate: "", publicGroup: { id: "public", name: "Common Room", description: "" },
} satisfies ServerInfo;

let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  vi.clearAllMocks();
});

function arrangeDependencies() {
  sdk.getAuthor.mockResolvedValue(author);
  sdk.getSeries.mockResolvedValue(series);
  sdk.listBooks.mockResolvedValue({ items: [], count: 0, next: null, previous: null });
  sdk.listAuthors.mockResolvedValue({ items: [], count: 0, next: null, previous: null });
  sdk.listSeries.mockResolvedValue({ items: [], count: 0, next: null, previous: null });
}

async function mount(kind: "author" | "series", id = `${kind}/id`, mode: "new" | "edit" = "edit") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const parameter = kind === "author" ? ":authorId" : ":seriesId";
  const route = `/library/${kind === "author" ? "authors" : "series"}/${parameter}/edit`;
  const initial = mode === "new"
    ? `/library/${kind === "author" ? "authors" : "series"}/new`
    : `/library/${kind === "author" ? "authors" : "series"}/${encodeURIComponent(id)}/edit`;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [
      { path: route, element: <AuthorSeriesEditOrchestrator kind={kind} mode="edit" /> },
      { path: `/library/${kind === "author" ? "authors" : "series"}/new`, element: <AuthorSeriesEditOrchestrator kind={kind} mode="new" /> },
      { path: "/library", element: <div data-testid="library-axis" /> },
    ],
  }], { initialEntries: [initial] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

async function setProse(container: HTMLElement, value: string) {
  await act(async () => buttonNamed(container, "Show raw").click());
  await act(async () => setControlValue(container.querySelector<HTMLTextAreaElement>("textarea#library-entity-prose")!, value));
}

describe("AuthorSeriesEditOrchestrator Author mutations", () => {
  it("loads and saves an Author biography while preventing a duplicate pending submit", async () => {
    arrangeDependencies();
    const pending = deferred<LibraryAuthor>();
    sdk.updateAuthor.mockReturnValue(pending.promise);
    const { container } = await mount("author");

    expect(sdk.getAuthor).toHaveBeenCalledWith("author/id");
    await setProse(container, "<p>Edited <strong>biography</strong></p>");
    act(() => submit(container.querySelector("form")!));

    expect(sdk.updateAuthor).toHaveBeenCalledWith("author/id", {
      name: "Ada Author", sortName: "Author, Ada", biography: "<p>Edited <strong>biography</strong></p>",
    });
    expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
    const sortNameInput = container.querySelector<HTMLInputElement>("#library-entity-sort-name")!;
    expect(sortNameInput.disabled).toBe(true);
    await act(async () => setControlValue(sortNameInput, "Newer sort name"));
    expect(sortNameInput.value).toBe("Author, Ada");
    act(() => submit(container.querySelector("form")!));
    buttonNamed(container, "Saving...").click();
    expect(sdk.updateAuthor).toHaveBeenCalledOnce();

    await act(async () => pending.resolve({ ...author, biography: "<p>Saved biography</p>" }));
    expect(container.querySelector<HTMLTextAreaElement>("textarea#library-entity-prose")?.value).toBe("<p>Saved biography</p>");
    expect(container.querySelector<HTMLInputElement>("#library-entity-sort-name")?.disabled).toBe(false);
  });

  it("keeps the Author draft after save failure and retries a failed initial load", async () => {
    arrangeDependencies();
    sdk.getAuthor.mockRejectedValueOnce(new Error("Author unavailable."));
    const failedSave = deferred<LibraryAuthor>();
    sdk.updateAuthor.mockReturnValueOnce(failedSave.promise).mockResolvedValueOnce({ ...author, biography: "<p>Unsaved biography</p>" });
    const { container } = await mount("author");

    await act(async () => buttonNamed(container, "Retry").click());
    await setProse(container, "<p>Unsaved biography</p>");
    act(() => submit(container.querySelector("form")!));
    expect(container.querySelector<HTMLInputElement>("#library-entity-name")?.disabled).toBe(true);
    await act(async () => failedSave.reject(new Error("Author save failed.")));

    expect(sdk.getAuthor).toHaveBeenCalledTimes(2);
    expect(container.querySelector<HTMLTextAreaElement>("textarea#library-entity-prose")?.value).toBe("<p>Unsaved biography</p>");
    expect(container.querySelector<HTMLInputElement>("#library-entity-name")?.disabled).toBe(false);
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
    await act(async () => submit(container.querySelector("form")!));
    expect(sdk.updateAuthor).toHaveBeenCalledTimes(2);
  });

  it("deletes an unattached Author only after confirmation and navigates to its axis", async () => {
    arrangeDependencies();
    sdk.deleteAuthor.mockResolvedValue(undefined);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount("author");

    await act(async () => buttonNamed(container, "Delete Author").click());

    expect(sdk.deleteAuthor).toHaveBeenCalledWith("author/id");
    expect(router.state.location.pathname).toBe("/library");
    expect(router.state.location.search).toBe("?view=authors");
  });

  it("retains the Author when deletion fails", async () => {
    arrangeDependencies();
    sdk.deleteAuthor.mockRejectedValue(new Error("Author delete failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount("author");

    await act(async () => buttonNamed(container, "Delete Author").click());

    expect(router.state.location.pathname).toContain("/authors/");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });
});

describe("AuthorSeriesEditOrchestrator Series mutations and shared request ownership", () => {
  it("loads and saves a Series summary from the authoritative response", async () => {
    arrangeDependencies();
    sdk.updateSeries.mockResolvedValue({ ...series, summary: "<p>Saved summary</p>" });
    const { container } = await mount("series");

    expect(sdk.getSeries).toHaveBeenCalledWith("series/id");
    await setProse(container, "<p>Edited <em>summary</em></p>");
    await act(async () => submit(container.querySelector("form")!));

    expect(sdk.updateSeries).toHaveBeenCalledWith("series/id", {
      name: "Example Series", sortName: "Example Series", summary: "<p>Edited <em>summary</em></p>",
    });
    expect(container.querySelector<HTMLTextAreaElement>("textarea#library-entity-prose")?.value).toBe("<p>Saved summary</p>");
  });

  it("keeps the Series draft after save failure and reports delete failure without navigating", async () => {
    arrangeDependencies();
    sdk.updateSeries.mockRejectedValue(new Error("Series save failed."));
    sdk.deleteSeries.mockRejectedValue(new Error("Series delete failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount("series");

    await setProse(container, "<p>Unsaved summary</p>");
    await act(async () => submit(container.querySelector("form")!));
    expect(container.querySelector<HTMLTextAreaElement>("textarea#library-entity-prose")?.value).toBe("<p>Unsaved summary</p>");

    await act(async () => buttonNamed(container, "Delete Series").click());
    expect(sdk.deleteSeries).toHaveBeenCalledWith("series/id");
    expect(router.state.location.pathname).toContain("/series/");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });

  it("deletes an unattached Series and navigates to the Series axis", async () => {
    arrangeDependencies();
    sdk.deleteSeries.mockResolvedValue(undefined);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, router } = await mount("series");

    await act(async () => buttonNamed(container, "Delete Series").click());

    expect(sdk.deleteSeries).toHaveBeenCalledWith("series/id");
    expect(router.state.location.pathname).toBe("/library");
    expect(router.state.location.search).toBe("?view=series");
  });

  it("ignores an old Author response after the route selects another identity", async () => {
    arrangeDependencies();
    const old = deferred<LibraryAuthor>();
    sdk.getAuthor.mockImplementation((id: string) => id === "old" ? old.promise : Promise.resolve({ ...author, id: "new", name: "New Author" }));
    const { container, router } = await mount("author", "old");

    await act(async () => router.navigate("/library/authors/new/edit"));
    expect(container.querySelector<HTMLInputElement>("#library-entity-name")?.value).toBe("New Author");
    await act(async () => old.resolve({ ...author, id: "old", name: "Old Author" }));
    expect(container.querySelector<HTMLInputElement>("#library-entity-name")?.value).toBe("New Author");
  });
});
