import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import type { ServerSettings } from "@second-pass/spl-api";
import { appRoutes, sectionRoutes } from "../app/router";
import { GeneralSettingsPageRegion } from "../features/server-settings/regions/GeneralSettingsPageRegion";
import { LibraryGroupsPageRegion } from "../features/server-settings/regions/LibraryGroupsPageRegion";
import { PublicLibraryPageRegion } from "../features/server-settings/regions/PublicLibraryPageRegion";
import { canAccessServerSettings, serverSettingsBreadcrumbFallback } from "../features/server-settings/ServerSettingsOrchestrator";
import { confirmEnableAdvancedGroups } from "../features/server-settings/serverSettingsConfirmations";
import { serverSettingsFormId, serverSettingsSearchParams, serverSettingsTabFromSearchParams } from "../features/server-settings/serverSettingsTabs";

const settings: ServerSettings = {
  general: { name: "Virgo SPL", description: "Private library", bannerText: "Maintenance" },
  publicLibrary: { name: "Common Room", description: "Shared books" },
  libraryGroups: { advancedGroupsEnabled: false },
};

describe("Server Settings", () => {
  it("owns /server as a base route with URL-backed tabs and no breadcrumb", () => {
    expect(sectionRoutes.map(({ path }) => path)).not.toContain("server");
    expect(appRoutes[0].children.some((route) => route.path === "server")).toBe(true);
    expect(serverSettingsBreadcrumbFallback).toEqual([]);
    expect(serverSettingsTabFromSearchParams(new URLSearchParams("tab=public-library"))).toBe("public-library");
    expect(serverSettingsTabFromSearchParams(new URLSearchParams("tab=invalid"))).toBe("general");
    expect(serverSettingsSearchParams("library-groups").toString()).toBe("tab=library-groups");
  });

  it("renders General read and bounded label/control edit states", () => {
    const read = renderToStaticMarkup(<GeneralSettingsPageRegion settings={settings.general} draft={settings.general} editing={false} state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    const edit = renderToStaticMarkup(<GeneralSettingsPageRegion settings={settings.general} draft={settings.general} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(read).toContain("Virgo SPL");
    expect(read).not.toContain("server-settings-name");
    expect(edit).toContain('class="form-field"');
    expect(edit).toContain('id="server-settings-name"');
    expect(serverSettingsFormId("general")).toBe("server-settings-general-form");
  });

  it("renders Public Library read/edit fields through its own form", () => {
    const edit = renderToStaticMarkup(<PublicLibraryPageRegion settings={settings.publicLibrary} draft={settings.publicLibrary} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(edit).toContain("Public group name");
    expect(edit).toContain("Public group description");
    expect(edit).toContain('id="server-settings-public-library-form"');
  });

  it("shows Enable only for disabled settings in edit mode and never renders Disable", () => {
    const render = (advancedGroupsEnabled: boolean, editing: boolean) => renderToStaticMarkup(<MemoryRouter><LibraryGroupsPageRegion settings={{ advancedGroupsEnabled }} editing={editing} state={{ pending: false }} onEnable={vi.fn()} /></MemoryRouter>);
    expect(render(false, false)).not.toContain("Enable Advanced Groups");
    expect(render(false, true)).toContain("Enable Advanced Groups");
    expect(render(true, true)).not.toContain("Enable Advanced Groups");
    expect(render(true, true)).not.toContain(">Disable<");
  });

  it("requires deliberate confirmation and recognizes Owner authority", () => {
    const cancelled = vi.fn(() => false);
    const accepted = vi.fn(() => true);
    expect(confirmEnableAdvancedGroups(cancelled)).toBe(false);
    expect(confirmEnableAdvancedGroups(accepted)).toBe(true);
    expect(cancelled).toHaveBeenCalledWith(expect.stringContaining("Service Hatch"));
    expect(canAccessServerSettings(true)).toBe(true);
    expect(canAccessServerSettings(false)).toBe(false);
  });
});
