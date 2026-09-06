/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Outlet, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";

const sdk = vi.hoisted(() => ({ changePassword: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  changeCurrentUserPassword: sdk.changePassword,
}));

import { PasswordChangeOrchestrator } from "../../../src/features/password-change/PasswordChangeOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

function user(mustChangePassword = false): CurrentUser {
  return { username: "reader", email: "", firstName: "", lastName: "", profileId: "profile", role: "reader", mustChangePassword, isOwner: false, isManager: false, isLibrarian: false, isReader: true, canAccessDjangoAdmin: false, groups: [] };
}

const server = { name: "Library" } as ServerInfo;

async function mountPasswordChange(mustChangePassword = false) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const refreshCurrentUser = vi.fn(async () => user(false));
  const context = { currentUser: user(mustChangePassword), serverInfo: server, refreshCurrentUser, refreshServerInfo: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  await act(async () => root?.render(
    <MemoryRouter initialEntries={["/profile/password"]}>
      <Routes><Route element={<Outlet context={context} />}><Route path="/profile/password" element={<PasswordChangeOrchestrator />} /><Route path="/profile" element={<div data-testid="profile" />} /></Route></Routes>
    </MemoryRouter>,
  ));
  return { container, refreshCurrentUser };
}

function enter(container: HTMLElement, id: string, value: string) {
  const input = container.querySelector<HTMLInputElement>(`#${id}`)!;
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("PasswordChangeOrchestrator", () => {
  it("submits credentials, refreshes identity, and leaves forced-change mode", async () => {
    sdk.changePassword.mockResolvedValue(undefined);
    const { container, refreshCurrentUser } = await mountPasswordChange(true);

    await act(async () => {
      enter(container, "current-password", "old-passphrase");
      enter(container, "new-password", "new-passphrase");
      enter(container, "confirm-password", "new-passphrase");
    });
    await act(async () => container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));

    expect(sdk.changePassword).toHaveBeenCalledWith({ currentPassword: "old-passphrase", newPassword: "new-passphrase", confirmPassword: "new-passphrase" });
    expect(refreshCurrentUser).toHaveBeenCalledOnce();
    expect(container.querySelector('[data-testid="profile"]')).not.toBeNull();
  });

  it("keeps entered state recoverable when the mutation fails", async () => {
    sdk.changePassword.mockRejectedValue(new Error("Password service unavailable."));
    const { container, refreshCurrentUser } = await mountPasswordChange();

    await act(async () => {
      enter(container, "current-password", "old-passphrase");
      enter(container, "new-password", "new-passphrase");
      enter(container, "confirm-password", "new-passphrase");
    });
    await act(async () => container.querySelector("form")?.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));

    expect(container.textContent).toContain("Password service unavailable.");
    expect(container.querySelector<HTMLInputElement>("#new-password")?.value).toBe("new-passphrase");
    expect(refreshCurrentUser).not.toHaveBeenCalled();
  });
});
