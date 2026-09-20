import type { GeneralServerSettings } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { FormField, KeyValueList } from "../../../components/UiPrimitives";
import { LimitedRichTextEditor } from "../../../components/LimitedRichTextEditor";
import { SanitizedRichText } from "../../../components/SanitizedRichText";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

export function GeneralSettingsPageRegion({ settings, serverUrls, draft, editing, state, onChange, onSubmit }: {
  settings: GeneralServerSettings;
  serverUrls: readonly string[];
  draft: GeneralServerSettings;
  editing: boolean;
  state: MutationState;
  onChange: (field: "name" | "description" | "bannerText", value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form id="server-settings-general-form" className="server-settings-form" aria-busy={state.pending} onSubmit={onSubmit}>
    <section className="server-settings-region server-settings-identity" aria-labelledby="server-identity-heading">
      <h2 id="server-identity-heading">Server Identity</h2>
      {editing ? <div className="form-grid server-settings-identity__form">
        <FormField label="Server name" htmlFor="server-settings-name" error={fieldError(state.error, "serverName")}><input id="server-settings-name" maxLength={120} required value={draft.name} disabled={state.pending} onChange={(event) => onChange("name", event.target.value)} /></FormField>
        <FormField label="Server description" htmlFor="server-settings-description" error={fieldError(state.error, "serverDescription")}><LimitedRichTextEditor id="server-settings-description" value={draft.description} disabled={state.pending} maxLength={1000} onChange={(value) => onChange("description", value)} /></FormField>
        <FormField label="Server banner message" htmlFor="server-settings-banner" error={fieldError(state.error, "serverBannerMessage")}><LimitedRichTextEditor id="server-settings-banner" value={draft.bannerText} disabled={state.pending} maxLength={500} onChange={(value) => onChange("bannerText", value)} /></FormField>
      </div> : <KeyValueList items={[
        { label: "Server name", value: settings.name },
        { label: "Server description", value: settings.description ? <SanitizedRichText html={settings.description} /> : "Empty" },
        { label: "Server banner message", value: settings.bannerText ? <SanitizedRichText html={settings.bannerText} className="server-settings-identity__banner" /> : "Empty" },
      ]} />}
    </section>
    <details className="server-settings-technical">
      <summary>Technical details</summary>
      <KeyValueList items={[
        { label: "Server ID", value: <code>{settings.serverId}</code> },
        { label: "Server URLs", value: serverUrls.length ? <ol>{serverUrls.map((url, index) => <li key={index}><code>{url}</code></li>)}</ol> : "None configured" },
      ]} />
      <p>Ordered by operator preference. Read-only deployment values.</p>
    </details>
  </form>;
}
