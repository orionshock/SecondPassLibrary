import type { GeneralServerSettings } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { FormField, KeyValueList } from "../../../components/UiPrimitives";
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
    <section className="server-settings-region" aria-labelledby="second-pass-reader-heading">
      <h2 id="second-pass-reader-heading">Second Pass Reader Web Client</h2>
      {editing ? <div className="form-grid">
        <FormField label="Second Pass Reader Web Client URL" htmlFor="server-settings-reader-web-client" error={fieldError(state.error, "secondPassReaderWebClientUrl")}>
          <input
            id="server-settings-reader-web-client"
            type="url"
            maxLength={2048}
            placeholder="https://reader.example.com"
            disabled={draft.secondPassReaderWebClientUrlLocked}
            value={draft.secondPassReaderWebClientUrl}
            onChange={(event) => onChange(event.target.value)}
          />
        </FormField>
        <p className="server-settings-help">Canonical base URL of the Second Pass Reader web client. Paths, queries, and fragments are removed. Leave blank to hide Open in Reader.</p>
        {draft.secondPassReaderWebClientUrlLocked ? <p className="server-settings-help">Configured by server environment.</p> : null}
      </div> : <KeyValueList items={[
        { label: "Second Pass Reader Web Client URL", value: settings.secondPassReaderWebClientUrl || "Disabled" },
        ...(settings.secondPassReaderWebClientUrlLocked ? [{ label: "Configuration", value: "Configured by server environment." }] : []),
      ]} />}
    </section>
  </form>;
}
