/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, MarginaliaBookSessionsPage, MarginaliaBookSummary, MarginaliaSessionListItem, Page, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { MarginaliaSessionsOrchestrator } from "../../../../src/features/marginalia/browse/MarginaliaSessionsOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ listSessions: vi.fn(), listBooks: vi.fn(), listBookSessions: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listMarginaliaSessions: sdk.listSessions,
  listMarginaliaBooks: sdk.listBooks,
  listMarginaliaBookSessions: sdk.listBookSessions,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const bookId = "11111111-1111-4111-8111-111111111111";
const book: MarginaliaBookSummary = {
  id: bookId, title: "Book Result", authors: [{ id: "author", name: "Author" }], series: null,
  coverUrl: null, canOpen: true, sessionCount: 1, activeSessionCount: 1, lastActivityAt: "2026-01-01T00:00:00Z",
};
const session = (id: string, name: string): MarginaliaSessionListItem => ({
  id, name, notes: "", status: "active", startedAt: "2026-01-01T00:00:00Z", closedAt: null,
  updatedAt: "2026-01-01T00:00:00Z", lastActivityAt: "2026-01-01T00:00:00Z", annotationCount: 1,
  book: { id: bookId, title: book.title, coverUrl: null, canOpen: true },
});
const page = <T,>(items: T[]): Page<T> => ({ items, count: items.length, next: null, previous: null });
const currentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader",
  mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true,
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

async function mount(path = "/marginalia") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/marginalia", element: <MarginaliaSessionsOrchestrator /> }],
  }], { initialEntries: [path] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, router };
}

describe("MarginaliaSessionsOrchestrator", () => {
  it("loads URL-backed Session filters and requests new results from edited controls", async () => {
    sdk.listSessions.mockResolvedValue(page([session("session-one", "Morning Notes")]));
    const { container } = await mount("/marginalia?q=notes&status=closed&page=2&page_size=30");

    expect(sdk.listSessions).toHaveBeenCalledWith({ q: "notes", status: "closed", page: 2, pageSize: 30 });
    act(() => {
      setControlValue(container.querySelector("#marginalia-search")!, "updated");
      submit(container.querySelector('[role="search"]')!);
    });
    await act(async () => undefined);
    expect(sdk.listSessions).toHaveBeenLastCalledWith({ q: "updated", page: 1, pageSize: 30 });
  });

  it("switches to Books and follows the existing Book-scoped Sessions state", async () => {
    sdk.listSessions.mockResolvedValue(page([]));
    sdk.listBooks.mockResolvedValue(page([book]));
    sdk.listBookSessions.mockResolvedValue({ ...page([]), book } satisfies MarginaliaBookSessionsPage);
    const { container } = await mount();

    const booksView = Array.from(container.querySelectorAll<HTMLButtonElement>('[role="group"][aria-label="Marginalia views"] button'))
      .find((button) => button.textContent?.endsWith("Books"));
    await act(async () => booksView?.click());
    expect(sdk.listBooks).toHaveBeenCalledWith({ page: 1, pageSize: 20 });
    const bookSessionsLink = container.querySelector(`a[href*="book=${bookId}"]`) as HTMLAnchorElement;
    await act(async () => bookSessionsLink.click());

    expect(sdk.listBookSessions).toHaveBeenCalledWith(bookId, { page: 1, pageSize: 20 });
    expect(container.querySelector('[aria-label="Selected Marginalia Book"]')).not.toBeNull();
  });

  it("retries a failed Session request and renders the recovered result", async () => {
    sdk.listSessions.mockRejectedValueOnce(new Error("History unavailable.")).mockResolvedValueOnce(page([session("recovered", "Recovered Session")]));
    const { container } = await mount();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();

    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listSessions).toHaveBeenCalledTimes(2);
    expect(container.querySelector('a[href="/marginalia/sessions/recovered"]')).not.toBeNull();
  });

  it("does not allow an older filter response to replace newer Sessions", async () => {
    const oldRequest = deferred<Page<MarginaliaSessionListItem>>();
    const newRequest = deferred<Page<MarginaliaSessionListItem>>();
    sdk.listSessions.mockReturnValueOnce(oldRequest.promise).mockReturnValueOnce(newRequest.promise);
    const { container, router } = await mount("/marginalia?q=old");

    await act(async () => router.navigate("/marginalia?q=new"));
    await act(async () => newRequest.resolve(page([session("new", "New Session")])));
    await act(async () => oldRequest.resolve(page([session("old", "Old Session")])));

    expect(container.querySelector('a[href="/marginalia/sessions/new"]')).not.toBeNull();
    expect(container.querySelector('a[href="/marginalia/sessions/old"]')).toBeNull();
  });
});
