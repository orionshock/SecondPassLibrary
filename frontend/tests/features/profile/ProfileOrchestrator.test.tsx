/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ClientSession, CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";
import { ProfileOrchestrator } from "../../../src/features/profile/ProfileOrchestrator";
import { buttonNamed, deferred } from "../../support/domInteraction";

const sdk = vi.hoisted(() => ({
  listSessions: vi.fn(), revokeSession: vi.fn(), revokeAll: vi.fn(), logoutOthers: vi.fn(), updateUser: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  listClientSessions: sdk.listSessions,
  revokeClientSession: sdk.revokeSession,
  revokeAllClientSessions: sdk.revokeAll,
  logoutOtherWebSessions: sdk.logoutOthers,
  updateCurrentUser: sdk.updateUser,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const user: CurrentUser = {
  username: "ada", email: "ada@example.test", firstName: "Ada", lastName: "Lovelace",
  profileId: "profile-id", role: "manager", mustChangePassword: false, isOwner: true,
  isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false,
  groups: [{ id: "public", name: "Common Room", isPublicGroup: true, isCurator: false }],
};
const serverInfo: ServerInfo = {
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: {
    id: "public", name: "Common Room", description: "",
  }, version: "dev", releaseDate: "",
};
const phone: ClientSession = {
  id: "phone-id", name: "Phone", clientType: "reader", createdAt: "created", updatedAt: "updated",
};
const tablet: ClientSession = {
  id: "tablet-id", name: "Tablet", clientType: "reader", createdAt: "created", updatedAt: "updated",
};
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

async function mount() {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const onCurrentUserChange = vi.fn();
  const context = {
    currentUser: user, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange, setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/profile", element: <ProfileOrchestrator /> }],
  }], { initialEntries: ["/profile"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return { container, onCurrentUserChange };
}

describe("ProfileOrchestrator account sessions", () => {
  it("loads connected client sessions through the browser-account SDK", async () => {
    sdk.listSessions.mockResolvedValue([phone, tablet]);
    const { container } = await mount();

    expect(sdk.listSessions).toHaveBeenCalledOnce();
    expect(container.querySelector('[aria-label="Revoke Phone"]')).not.toBeNull();
    expect(container.querySelector('[aria-label="Revoke Tablet"]')).not.toBeNull();
  });

  it("revokes one device, prevents duplicate actions while pending, and removes it only after success", async () => {
    sdk.listSessions.mockResolvedValue([phone, tablet]);
    const pending = deferred<void>();
    sdk.revokeSession.mockReturnValue(pending.promise);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container } = await mount();

    act(() => buttonNamed(container, "Revoke Phone").click());
    expect(sdk.revokeSession).toHaveBeenCalledWith("phone-id");
    expect(buttonNamed(container, "Revoke Tablet").disabled).toBe(true);
    expect(container.textContent).toContain("Phone");

    await act(async () => pending.resolve());
    expect(container.querySelector('[aria-label="Revoke Phone"]')).toBeNull();
    expect(container.querySelector('[aria-label="Revoke Tablet"]')).not.toBeNull();
  });

  it("leaves a device visible when its revoke request fails", async () => {
    sdk.listSessions.mockResolvedValue([phone]);
    sdk.revokeSession.mockRejectedValue(new Error("Device revoke failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Revoke Phone").click());

    expect(container.textContent).toContain("Phone");
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });

  it("gates bulk disconnection, clears devices after success, and keeps the browser account active", async () => {
    sdk.listSessions.mockResolvedValue([phone, tablet]);
    const confirm = vi.fn(() => false);
    vi.stubGlobal("confirm", confirm);
    const pending = deferred<void>();
    sdk.revokeAll.mockReturnValue(pending.promise);
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Disconnect all devices and apps").click());
    expect(sdk.revokeAll).not.toHaveBeenCalled();
    confirm.mockReturnValue(true);
    act(() => buttonNamed(container, "Disconnect all devices and apps").click());
    expect(sdk.revokeAll).toHaveBeenCalledOnce();
    expect(buttonNamed(container, "Disconnecting…").disabled).toBe(true);
    expect(container.textContent).toContain("Phone");

    await act(async () => pending.resolve());
    expect(container.querySelector('[aria-label="Revoke Phone"]')).toBeNull();
    expect(container.querySelector('a[href="/profile/password"]')).not.toBeNull();
    expect(container.textContent).toContain("ada@example.test");
  });

  it("does not falsely clear devices when bulk disconnection fails", async () => {
    sdk.listSessions.mockResolvedValue([phone]);
    sdk.revokeAll.mockRejectedValue(new Error("Bulk revoke failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Disconnect all devices and apps").click());

    expect(container.querySelector('[aria-label="Revoke Phone"]')).not.toBeNull();
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });

  it("logs out other web sessions without changing the current browser identity", async () => {
    sdk.listSessions.mockResolvedValue([]);
    sdk.logoutOthers.mockResolvedValue(undefined);
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container, onCurrentUserChange } = await mount();

    await act(async () => buttonNamed(container, "Log out other web sessions").click());

    expect(sdk.logoutOthers).toHaveBeenCalledOnce();
    expect(onCurrentUserChange).not.toHaveBeenCalled();
    expect(container.textContent).toContain("ada@example.test");
  });

  it("keeps the current browser usable when web-session revocation fails", async () => {
    sdk.listSessions.mockResolvedValue([]);
    sdk.logoutOthers.mockRejectedValue(new Error("Web-session revoke failed."));
    vi.stubGlobal("confirm", vi.fn(() => true));
    const { container } = await mount();

    await act(async () => buttonNamed(container, "Log out other web sessions").click());

    expect(container.querySelector('a[href="/profile/password"]')).not.toBeNull();
    expect(container.querySelector("[role=\"alert\"]")).not.toBeNull();
  });
});
