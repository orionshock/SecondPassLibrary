import type { GeneralServerSettings } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { FormField, KeyValueList } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

export function GeneralSettingsPageRegion({ settings, draft, editing, state, onChange, onSubmit }: {
  settings: GeneralServerSettings;
  draft: GeneralServerSettings;
  editing: boolean;
  state: MutationState;
  onChange: (field: "name" | "description" | "bannerText", value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form id="server-settings-general-form" className="server-settings-form" onSubmit={onSubmit}>
    <section className="server-settings-region" aria-labelledby="server-identity-heading">
      <h2 id="server-identity-heading">Server identity</h2>
      {editing ? <div className="form-grid">
        <FormField label="Server name" htmlFor="server-settings-name" error={fieldError(state.error, "serverName")}><input id="server-settings-name" maxLength={120} required value={draft.name} onChange={(event) => onChange("name", event.target.value)} /></FormField>
        <FormField label="Server description" htmlFor="server-settings-description" error={fieldError(state.error, "serverDescription")}><textarea id="server-settings-description" maxLength={1000} rows={4} value={draft.description} onChange={(event) => onChange("description", event.target.value)} /></FormField>
      </div> : <KeyValueList items={[{ label: "Server name", value: settings.name }, { label: "Server description", value: settings.description || "Empty" }]} />}
    </section>
    <section className="server-settings-region" aria-labelledby="server-banner-heading">
      <h2 id="server-banner-heading">Banner</h2>
      {editing ? <div className="form-grid"><FormField label="Banner text" htmlFor="server-settings-banner" error={fieldError(state.error, "serverBannerMessage")}><textarea id="server-settings-banner" maxLength={500} rows={4} value={draft.bannerText} onChange={(event) => onChange("bannerText", event.target.value)} /></FormField></div> : <KeyValueList items={[{ label: "Banner text", value: settings.bannerText || "Empty" }]} />}
    </section>
  </form>;
}
