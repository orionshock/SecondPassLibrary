import { resolveTabQuery, withTabQuery } from "../../app/routing/tabQuery";

export type ServerSettingsTab = "general" | "public-library" | "external-services" | "library-groups";

export const serverSettingsTabs: readonly { id: ServerSettingsTab; label: string }[] = [
  { id: "general", label: "General" },
  { id: "public-library", label: "Public Library" },
  { id: "external-services", label: "External Services" },
  { id: "library-groups", label: "Advanced Library Groups" },
];

export function serverSettingsTabFromSearchParams(parameters: URLSearchParams): ServerSettingsTab {
  return resolveTabQuery(parameters, serverSettingsTabs.map(({ id }) => id), "general").tab;
}

export function serverSettingsSearchParams(
  parameters: URLSearchParams,
  tab: ServerSettingsTab,
): URLSearchParams {
  return withTabQuery(parameters, tab, "general");
}

export function serverSettingsFormId(tab: ServerSettingsTab): string | undefined {
  if (tab === "general") return "server-settings-general-form";
  if (tab === "public-library") return "server-settings-public-library-form";
  if (tab === "external-services") return "server-settings-external-services-form";
  return undefined;
}
