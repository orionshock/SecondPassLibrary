/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter, Outlet, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { CurrentUser, ServerInfo, ServerSettings } from "@second-pass/spl-api";
import type { AppOutletContext } from "../../../src/app/layout/AppOrchestrator";

const sdk = vi.hoisted(() => ({
  getSettings: vi.fn(),
  updateIdentity: vi.fn(),
  updateExternal: vi.fn(),
  updatePublic: vi.fn(),
  enableGroups: vi.fn(),
}));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  getServerSettings: sdk.getSettings,
  updateServerIdentity: sdk.updateIdentity,
  updateExternalServicesSettings: sdk.updateExternal,
  updatePublicLibrarySettings: sdk.updatePublic,
  enableAdvancedGroups: sdk.enableGroups,
}));

import { ServerSettingsOrchestrator } from "../../../src/features/server-settings/ServerSettingsOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

const settings: ServerSettings = {
  general: { serverId: "server-id", name: "Virgo SPL", description: "<p>Private <strong>library</strong></p>", bannerText: "<p><em>Maintenance</em></p>", secondPassReaderWebClientUrl: "https://reader.example.com", secondPassReaderWebClientUrlLocked: false },
  publicLibrary: { name: "Common Room", description: "<p>Shared books</p>" },
  libraryGroups: { advancedGroupsEnabled: false },
};
const currentUser = { username: "owner", isOwner: true, canAccessDjangoAdmin: true } as CurrentUser;
const serverInfo = { name: "Virgo SPL", serverUrls: ["https://library.home.example", "https://library.public.example"] } as ServerInfo;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mountSettings(refreshServerInfo = vi.fn(async () => serverInfo)) {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  const context = { currentUser, serverInfo, refreshServerInfo, refreshCurrentUser: vi.fn(), onCurrentUserChange: vi.fn(), setBreadcrumbs: vi.fn() } satisfies AppOutletContext;
  await act(async () => root?.render(
    <MemoryRouter initialEntries={["/server"]}>
      <Routes><Route element={<Outlet context={context} />}><Route path="/server" element={<ServerSettingsOrchestrator />} /></Route></Routes>
    </MemoryRouter>,
  ));
  return { container, refreshServerInfo };
}

function button(container: HTMLElement, text: string) {
  return Array.from(container.querySelectorAll("button")).find((candidate) => candidate.textContent === text);
}

function changeInput(input: HTMLInputElement, value: string) {
  Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, value);
  input.dispatchEvent(new Event("input", { bubbles: true }));
}

describe("ServerSettingsOrchestrator", () => {
  it("shows the authenticated server URLs in operator order", async () => {
    sdk.getSettings.mockResolvedValue(settings);
    const { container } = await mountSettings();
    const details = container.querySelector("details");

    expect(details?.open).toBe(false);
    details?.querySelector("summary")?.click();
    expect(Array.from(details?.querySelectorAll("ol li code") ?? [], (code) => code.textContent)).toEqual(serverInfo.serverUrls);
  });

  it("loads and saves Server Identity as one mutation while preserving rich values", async () => {
    sdk.getSettings.mockResolvedValue(settings);
    sdk.updateIdentity.mockResolvedValue({ ...settings, general: { ...settings.general, name: "Updated Library" } });
    const { container, refreshServerInfo } = await mountSettings();

    expect(sdk.getSettings).toHaveBeenCalledOnce();
    await act(async () => button(container, "Edit")?.click());
    await act(async () => changeInput(container.querySelector<HTMLInputElement>("#server-settings-name")!, "Updated Library"));
    await act(async () => button(container, "Save")?.click());

    expect(sdk.updateIdentity).toHaveBeenCalledWith({ ...settings.general, name: "Updated Library" });
    expect(refreshServerInfo).toHaveBeenCalledOnce();
    expect(container.querySelector("#server-settings-name")).toBeNull();
    expect(container.textContent).toContain("Updated Library");
  });

  it("keeps the editable draft and reports failure without claiming success", async () => {
    sdk.getSettings.mockResolvedValue(settings);
    sdk.updateIdentity.mockRejectedValue(new Error("Settings could not be saved."));
    const { container, refreshServerInfo } = await mountSettings();

    await act(async () => button(container, "Edit")?.click());
    await act(async () => changeInput(container.querySelector<HTMLInputElement>("#server-settings-name")!, "Unsaved Library"));
    await act(async () => button(container, "Save")?.click());

    expect(container.querySelector<HTMLInputElement>("#server-settings-name")?.value).toBe("Unsaved Library");
    expect(container.textContent).toContain("Settings could not be saved.");
    expect(container.textContent).not.toContain("Server identity saved.");
    expect(refreshServerInfo).not.toHaveBeenCalled();
  });

  it("reports a shell refresh failure without reporting the committed write as failed", async () => {
    sdk.getSettings.mockResolvedValue(settings);
    sdk.updateIdentity.mockResolvedValue({ ...settings, general: { ...settings.general, name: "Updated Library" } });
    const refreshServerInfo = vi.fn(async () => { throw new Error("Refresh failed."); });
    const consoleWarning = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const { container } = await mountSettings(refreshServerInfo);

    await act(async () => button(container, "Edit")?.click());
    await act(async () => changeInput(container.querySelector<HTMLInputElement>("#server-settings-name")!, "Updated Library"));
    await act(async () => button(container, "Save")?.click());

    expect(container.textContent).toContain("Server identity saved.");
    expect(container.textContent).toContain("Settings were saved, but the application shell could not be refreshed.");
    expect(container.textContent).not.toContain("Refresh failed.");
    expect(consoleWarning).toHaveBeenCalledWith(
      "Server settings were saved, but the application shell refresh failed.",
      { failureClass: "Error" },
    );
  });

  it("disables the grouped save while the identity mutation is pending", async () => {
    sdk.getSettings.mockResolvedValue(settings);
    let resolveSave!: (value: ServerSettings) => void;
    sdk.updateIdentity.mockReturnValue(new Promise<ServerSettings>((resolve) => { resolveSave = resolve; }));
    const { container } = await mountSettings();

    await act(async () => button(container, "Edit")?.click());
    act(() => button(container, "Save")?.click());

    expect(container.querySelector<HTMLButtonElement>('button[type="submit"]')?.disabled).toBe(true);
    await act(async () => resolveSave(settings));
  });

  it("keeps external-service changes on their separate SDK operation", async () => {
    sdk.getSettings.mockResolvedValue(settings);
    sdk.updateExternal.mockResolvedValue(settings);
    const { container } = await mountSettings();

    await act(async () => button(container, "External Services")?.click());
    await act(async () => button(container, "Edit")?.click());
    await act(async () => button(container, "Save")?.click());

    expect(sdk.updateExternal).toHaveBeenCalledWith("https://reader.example.com");
    expect(sdk.updateIdentity).not.toHaveBeenCalled();
  });
});
