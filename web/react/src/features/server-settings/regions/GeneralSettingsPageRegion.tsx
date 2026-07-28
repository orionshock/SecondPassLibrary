import type { GeneralServerSettings } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { FormField, KeyValueList } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

export function GeneralSettingsPageRegion({ settings, draft, editing, state, onChange, onSubmit }: {
  settings: GeneralServerSettings;
  draft: GeneralServerSettings;
  editing: boolean;
  state: MutationState;
  onChange: (field: "name" | "description" | "bannerText" | "readingClientBaseUrl", value: string) => void;
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
    <section className="server-settings-region" aria-labelledby="reading-client-heading">
      <h2 id="reading-client-heading">Reading Client</h2>
      {editing ? <div className="form-grid">
        <FormField label="Reading Client URL" htmlFor="server-settings-reading-client" error={fieldError(state.error, "readingClientBaseUrl")}>
          <input
            id="server-settings-reading-client"
            type="url"
            maxLength={2048}
            placeholder="https://reader.example.com"
            disabled={draft.readingClientBaseUrlLocked}
            value={draft.readingClientBaseUrl}
            onChange={(event) => onChange("readingClientBaseUrl", event.target.value)}
          />
        </FormField>
        <p className="server-settings-help">Root URL of the Reading Client. Leave blank to hide Open in Reader.</p>
        {draft.readingClientBaseUrlLocked ? <p className="server-settings-help">Configured by server environment.</p> : null}
      </div> : <KeyValueList items={[
        { label: "Reading Client URL", value: settings.readingClientBaseUrl || "Disabled" },
        ...(settings.readingClientBaseUrlLocked ? [{ label: "Configuration", value: "Configured by server environment." }] : []),
      ]} />}
    </section>
  </form>;
}
