/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";

const sdk = vi.hoisted(() => ({ logout: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  logoutCurrentWebSession: sdk.logout,
}));

import { AppOrchestrator } from "../../src/app/layout/AppOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

const user: CurrentUser = { username: "owner", email: "", firstName: "", lastName: "", profileId: "profile", role: "manager", mustChangePassword: false, isOwner: true, isManager: false, isLibrarian: false, isReader: false, canAccessDjangoAdmin: false, groups: [] };
const server: ServerInfo = { serverId: "server-id", serverUrls: [], name: "Family Library", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.restoreAllMocks();
});

describe("AppOrchestrator logout", () => {
  it("keeps the authenticated shell and reports when logout fails", async () => {
    sdk.logout.mockRejectedValue(new Error("Request failed."));
    const consoleWarning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const container = document.createElement("div");
    document.body.append(container);
    root = createRoot(container);
    await act(async () => root?.render(
      <MemoryRouter><AppOrchestrator user={user} server={server} onCurrentUserChange={vi.fn()} /></MemoryRouter>,
    ));

    await act(async () => container.querySelector<HTMLButtonElement>('[aria-label="Open account menu for owner"]')?.click());
    const logout = Array.from(container.querySelectorAll("button")).find((candidate) => candidate.textContent?.includes("Log out"));
    await act(async () => logout?.click());

    expect(sdk.logout).toHaveBeenCalledOnce();
    expect(container.textContent).toContain("Family Library");
    expect(container.textContent).toContain("Log out failed. Your session may still be active. Try again.");
    expect(container.textContent).not.toContain("Request failed.");
    expect(consoleWarning).toHaveBeenCalledWith(
      "Logout failed; the browser session may still be active.",
      { failureClass: "Error" },
    );
  });
});
