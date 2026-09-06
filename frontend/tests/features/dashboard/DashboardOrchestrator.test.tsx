/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, RecentMarginaliaSession, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";
import { DashboardOrchestrator } from "../../../src/features/dashboard/DashboardOrchestrator";
import { buttonNamed } from "../../support/domInteraction";

const sdk = vi.hoisted(() => ({ listRecentSessions: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listRecentMarginaliaSessions: sdk.listRecentSessions,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
const session: RecentMarginaliaSession = {
  id: "session", name: "Current Read", status: "active", lastActivityAt: "2026-09-06T00:00:00Z", progress: null,
  book: { id: "book", title: "Current Book", coverUrl: null, canOpen: true },
};
const owner = {
  username: "owner", email: "", firstName: "", lastName: "", profileId: "owner", role: "manager",
  mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
} satisfies CurrentUser;
const serverInfo = {
  name: "Library", description: "", bannerText: "<p>Planned <strong>maintenance</strong></p>", advancedLibraryGroupsEnabled: true,
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

async function mount(currentUser: CurrentUser = owner) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = { currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  const router = createMemoryRouter([{ element: <Outlet context={context} />, children: [{ path: "/", element: <DashboardOrchestrator /> }] }], { initialEntries: ["/"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return container;
}

describe("DashboardOrchestrator", () => {
  it("loads bounded recent Sessions and renders their detail destinations", async () => {
    sdk.listRecentSessions.mockResolvedValue([session]);
    const container = await mount();

    expect(sdk.listRecentSessions).toHaveBeenCalledWith({ limit: 50 });
    expect(container.querySelector('a[href="/marginalia/sessions/session"]')).not.toBeNull();
    expect(container.querySelector('aside[aria-label="Server message"] strong')?.textContent).toBe("maintenance");
  });

  it("retries a recoverable recent-reading failure", async () => {
    sdk.listRecentSessions.mockRejectedValueOnce(new Error("Recent reading unavailable.")).mockResolvedValueOnce([session]);
    const container = await mount();

    expect(container.querySelector('[role="alert"]')?.textContent).toContain("Recent reading unavailable.");
    await act(async () => buttonNamed(container, "Retry").click());

    expect(sdk.listRecentSessions).toHaveBeenCalledTimes(2);
    expect(container.querySelector('a[href="/marginalia/sessions/session"]')).not.toBeNull();
  });

  it("keeps operator destinations gated for a Reader while retaining reader workflows", async () => {
    sdk.listRecentSessions.mockResolvedValue([]);
    const reader = { ...owner, role: "reader", isOwner: false, isReader: true } satisfies CurrentUser;
    const container = await mount(reader);

    expect(container.querySelector('a[href="/imports"]')).toBeNull();
    expect(container.querySelector('a[href="/users"]')).toBeNull();
    expect(container.querySelector('a[href="/server"]')).toBeNull();
    expect(container.querySelector('a[href="/library"]')).not.toBeNull();
    expect(container.querySelector('a[href="/shelves"]')).not.toBeNull();
  });
});
