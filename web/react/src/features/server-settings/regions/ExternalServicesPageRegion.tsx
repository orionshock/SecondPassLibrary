import type { GeneralServerSettings } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { FormField, KeyValueList } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

export function ExternalServicesPageRegion({ settings, draft, editing, state, onChange, onSubmit }: {
  settings: GeneralServerSettings;
  draft: GeneralServerSettings;
  editing: boolean;
  state: MutationState;
  onChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form id="server-settings-external-services-form" className="server-settings-form" onSubmit={onSubmit}>
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
            onChange={(event) => onChange(event.target.value)}
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
