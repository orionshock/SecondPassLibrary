import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { ApiError, type ServerSettings } from "@second-pass/spl-api";
import { appRoutes, sectionRoutes } from "../app/router";
import { ExternalServicesPageRegion } from "../features/server-settings/regions/ExternalServicesPageRegion";
import { GeneralSettingsPageRegion } from "../features/server-settings/regions/GeneralSettingsPageRegion";
import { LibraryGroupsPageRegion } from "../features/server-settings/regions/LibraryGroupsPageRegion";
import { PublicLibraryPageRegion } from "../features/server-settings/regions/PublicLibraryPageRegion";
import { canAccessServerSettings, serverSettingsBreadcrumbFallback } from "../features/server-settings/ServerSettingsOrchestrator";
import { confirmEnableAdvancedGroups } from "../features/server-settings/serverSettingsConfirmations";
import { DjangoAdminAction } from "../features/server-settings/DjangoAdminAction";
import { serverSettingsFormId, serverSettingsSearchParams, serverSettingsTabFromSearchParams, serverSettingsTabs } from "../features/server-settings/serverSettingsTabs";

const settings: ServerSettings = {
  general: { name: "Virgo SPL", description: "Private library", bannerText: "Maintenance", readingClientBaseUrl: "https://reader.example.com", readingClientBaseUrlLocked: false },
  publicLibrary: { name: "Common Room", description: "Shared books" },
  libraryGroups: { advancedGroupsEnabled: false },
};

describe("Server Settings", () => {
  it("owns /server as a base route with URL-backed tabs and no breadcrumb", () => {
    expect(sectionRoutes.map(({ path }) => path)).not.toContain("server");
    expect(appRoutes[0].children.some((route) => route.path === "server")).toBe(true);
    expect(serverSettingsBreadcrumbFallback).toEqual([]);
    expect(serverSettingsTabFromSearchParams(new URLSearchParams())).toBe("general");
    expect(serverSettingsTabFromSearchParams(new URLSearchParams("tab=public-library"))).toBe("public-library");
    expect(serverSettingsTabFromSearchParams(new URLSearchParams("tab=external-services"))).toBe("external-services");
    expect(serverSettingsTabFromSearchParams(new URLSearchParams("tab=library-groups"))).toBe("library-groups");
    expect(serverSettingsTabFromSearchParams(new URLSearchParams("tab=invalid"))).toBe("general");
    expect(serverSettingsSearchParams(new URLSearchParams("trail=context&tab=general"), "general").toString()).toBe("trail=context");
    expect(serverSettingsSearchParams(new URLSearchParams("trail=context"), "external-services").toString()).toBe("trail=context&tab=external-services");
    expect(serverSettingsSearchParams(new URLSearchParams("trail=context"), "library-groups").toString()).toBe("trail=context&tab=library-groups");
    expect(serverSettingsTabs).toEqual([
      { id: "general", label: "General" },
      { id: "public-library", label: "Public Library" },
      { id: "external-services", label: "External Services" },
      { id: "library-groups", label: "Advanced Library Groups" },
    ]);
  });

  it("renders General read and bounded label/control edit states", () => {
    const read = renderToStaticMarkup(<GeneralSettingsPageRegion settings={settings.general} draft={settings.general} editing={false} state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    const edit = renderToStaticMarkup(<GeneralSettingsPageRegion settings={settings.general} draft={settings.general} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(read).toContain("Virgo SPL");
    expect(read).not.toContain("server-settings-name");
    expect(edit).toContain('class="form-field"');
    expect(edit).toContain('id="server-settings-name"');
    expect(edit).not.toContain('id="server-settings-reading-client"');
    expect(edit).not.toContain("disabled");
    expect(serverSettingsFormId("general")).toBe("server-settings-general-form");
  });

  it("owns Reading Client state only in External Services and preserves locking", () => {
    const general = renderToStaticMarkup(<GeneralSettingsPageRegion settings={settings.general} draft={settings.general} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    const read = renderToStaticMarkup(<ExternalServicesPageRegion settings={settings.general} draft={settings.general} editing={false} state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    const edit = renderToStaticMarkup(<ExternalServicesPageRegion settings={settings.general} draft={settings.general} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    const locked = { ...settings.general, readingClientBaseUrlLocked: true };
    const lockedEdit = renderToStaticMarkup(<ExternalServicesPageRegion settings={locked} draft={locked} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    const invalid = renderToStaticMarkup(<ExternalServicesPageRegion
      settings={settings.general}
      draft={settings.general}
      editing
      state={{ pending: false, error: new ApiError("Invalid settings.", 400, { fields: { readingClientBaseUrl: ["Invalid URL."] } }) }}
      onChange={vi.fn()}
      onSubmit={vi.fn()}
    />);
    expect(general).not.toContain("server-settings-reading-client");
    expect(read).toContain("https://reader.example.com");
    expect(read).not.toContain("server-settings-reading-client");
    expect(edit).toContain('id="server-settings-reading-client"');
    expect(edit).toContain('value="https://reader.example.com"');
    expect(edit).not.toContain("disabled");
    expect(lockedEdit).toMatch(/id="server-settings-reading-client"[^>]*disabled/);
    expect(invalid).toContain('class="field-error"');
    expect(serverSettingsFormId("external-services")).toBe("server-settings-external-services-form");
  });

  it("renders Public Library read/edit fields through its own form", () => {
    const edit = renderToStaticMarkup(<PublicLibraryPageRegion settings={settings.publicLibrary} draft={settings.publicLibrary} editing state={{ pending: false }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(edit).toContain('id="server-settings-public-name"');
    expect(edit).toContain('id="server-settings-public-description"');
    expect(edit).toContain('id="server-settings-public-library-form"');
  });

  it("consumes settings field errors through app-facing names", () => {
    const error = new ApiError("Invalid settings.", 400, { fields: { publicGroupName: ["Choose another name."] } });
    const edit = renderToStaticMarkup(<PublicLibraryPageRegion settings={settings.publicLibrary} draft={settings.publicLibrary} editing state={{ pending: false, error }} onChange={vi.fn()} onSubmit={vi.fn()} />);
    expect(edit).toContain("Choose another name.");
  });

  it("shows the one-way action only for disabled settings in edit mode", () => {
    const render = (advancedGroupsEnabled: boolean, editing: boolean) => renderToStaticMarkup(<MemoryRouter><LibraryGroupsPageRegion settings={{ advancedGroupsEnabled }} editing={editing} state={{ pending: false }} onEnable={vi.fn()} /></MemoryRouter>);
    expect(render(false, false)).not.toContain("<button");
    expect(render(false, true)).toMatch(/<button[^>]*type="button"/);
    expect(render(true, true)).not.toContain("<button");
    expect(render(false, true)).toContain("server-settings-region--centered");
  });

  it("requires deliberate confirmation and recognizes Owner authority", () => {
    const cancelled = vi.fn(() => false);
    const accepted = vi.fn(() => true);
    expect(confirmEnableAdvancedGroups(cancelled)).toBe(false);
    expect(confirmEnableAdvancedGroups(accepted)).toBe(true);
    expect(cancelled).toHaveBeenCalledOnce();
    expect(canAccessServerSettings(true)).toBe(true);
    expect(canAccessServerSettings(false)).toBe(false);
  });

  it("renders the Django Admin action only when capability allows it", () => {
    expect(renderToStaticMarkup(<DjangoAdminAction enabled />)).toContain('href="/admin/"');
    expect(renderToStaticMarkup(<DjangoAdminAction enabled={false} />)).toBe("");
  });
});
