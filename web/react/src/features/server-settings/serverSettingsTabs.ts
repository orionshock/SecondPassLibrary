export type ServerSettingsTab = "general" | "public-library" | "library-groups";

export const serverSettingsTabs: readonly { id: ServerSettingsTab; label: string }[] = [
  { id: "general", label: "General" },
  { id: "public-library", label: "Public Library" },
  { id: "library-groups", label: "Library Groups" },
];

export function serverSettingsTabFromSearchParams(parameters: URLSearchParams): ServerSettingsTab {
  const value = parameters.get("tab");
  return serverSettingsTabs.some(({ id }) => id === value) ? value as ServerSettingsTab : "general";
}

export function serverSettingsSearchParams(tab: ServerSettingsTab): URLSearchParams {
  return new URLSearchParams({ tab });
}

export function serverSettingsFormId(tab: ServerSettingsTab): string | undefined {
  if (tab === "general") return "server-settings-general-form";
  if (tab === "public-library") return "server-settings-public-library-form";
  return undefined;
}
