/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { createMemoryRouter, Outlet, RouterProvider } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CreateUserResult, CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../../src/app/layout/AppOrchestrator";
import { UserCreateOrchestrator } from "../../../../src/features/users/create/UserCreateOrchestrator";
import { buttonNamed, deferred, setControlValue, submit } from "../../../support/domInteraction";

const sdk = vi.hoisted(() => ({ createUser: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  createUser: sdk.createUser,
}));

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;

const owner: CurrentUser = {
  username: "owner", email: "", firstName: "", lastName: "", profileId: "owner-id", role: "manager",
  mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false,
  canAccessDjangoAdmin: false, groups: [],
};
const serverInfo: ServerInfo = {
  name: "Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: true,
  secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", version: "dev", releaseDate: "",
  publicGroup: { id: "public", name: "Common Room", description: "" },
};
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
  const context = {
    currentUser, serverInfo, refreshCurrentUser: vi.fn(), refreshServerInfo: vi.fn(),
    onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn(),
  } satisfies AppOutletContext;
  const router = createMemoryRouter([{
    element: <Outlet context={context} />,
    children: [{ path: "/users/new", element: <UserCreateOrchestrator /> }],
  }], { initialEntries: ["/users/new"] });
  await act(async () => root?.render(<RouterProvider router={router} />));
  return container;
}

describe("UserCreateOrchestrator", () => {
  it("submits the editable account fields once and presents the authoritative temporary credentials", async () => {
    const pending = deferred<CreateUserResult>();
    sdk.createUser.mockReturnValue(pending.promise);
    const container = await mount();
    act(() => {
      setControlValue(container.querySelector("#user-create-username")!, "new-reader");
      setControlValue(container.querySelector("#user-create-email")!, "reader@example.test");
      setControlValue(container.querySelector("#user-create-first-name")!, "New");
      setControlValue(container.querySelector("#user-create-last-name")!, "Reader");
      setControlValue(container.querySelector("#user-create-role")!, "reader");
      submit(container.querySelector("form")!);
    });
    expect(sdk.createUser).toHaveBeenCalledWith({
      username: "new-reader", email: "reader@example.test", firstName: "New", lastName: "Reader", role: "reader",
    });
    expect(buttonNamed(container, "Creating...").disabled).toBe(true);
    act(() => buttonNamed(container, "Creating...").click());
    expect(sdk.createUser).toHaveBeenCalledOnce();

    await act(async () => pending.resolve({
      user: {
        id: "created-id", username: "new-reader", email: "reader@example.test", firstName: "New", lastName: "Reader",
        role: "reader", isOwner: false, isActive: true, dateJoined: "now", lastLogin: null,
        mustChangePassword: true, groups: [],
      },
      temporaryPassword: "one-time-password", message: "Created",
    }));
    expect((container.querySelector("#created-user-temporary-password") as HTMLTextAreaElement | null)?.value).toContain("one-time-password");
    expect(container.querySelector('a[href="/users/created-id/edit"]')).not.toBeNull();
  });

  it("keeps the entered draft available when creation fails", async () => {
    sdk.createUser.mockRejectedValue(new Error("Creation failed."));
    const container = await mount();
    const username = container.querySelector("#user-create-username") as HTMLInputElement;
    act(() => setControlValue(username, "recoverable-reader"));

    await act(async () => submit(container.querySelector("form")!));

    expect(username.value).toBe("recoverable-reader");
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(buttonNamed(container, "Create User").disabled).toBe(false);
  });

  it("does not expose or invoke account creation for an unauthorized operator", async () => {
    const reader = { ...owner, isOwner: false, role: "reader", isReader: true } satisfies CurrentUser;
    const container = await mount(reader);

    expect(container.querySelector("form")).toBeNull();
    expect(container.querySelector('[role="alert"]')).not.toBeNull();
    expect(sdk.createUser).not.toHaveBeenCalled();
  });
});
