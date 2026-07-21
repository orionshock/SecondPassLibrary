import type { PublicLibrarySettings } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { FormField, KeyValueList } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

export function PublicLibraryPageRegion({ settings, draft, editing, state, onChange, onSubmit }: {
  settings: PublicLibrarySettings;
  draft: PublicLibrarySettings;
  editing: boolean;
  state: MutationState;
  onChange: (field: keyof PublicLibrarySettings, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form id="server-settings-public-library-form" className="server-settings-form" onSubmit={onSubmit}>
    <section className="server-settings-region" aria-labelledby="public-library-heading">
      <h2 id="public-library-heading">Public Library</h2>
      {editing ? <div className="form-grid">
        <FormField label="Public group name" htmlFor="server-settings-public-name" error={fieldError(state.error, "public_group_name")}><input id="server-settings-public-name" required maxLength={255} value={draft.name} onChange={(event) => onChange("name", event.target.value)} /></FormField>
        <FormField label="Public group description" htmlFor="server-settings-public-description" error={fieldError(state.error, "public_group_description")}><textarea id="server-settings-public-description" rows={4} value={draft.description} onChange={(event) => onChange("description", event.target.value)} /></FormField>
      </div> : <KeyValueList items={[{ label: "Public group name", value: settings.name }, { label: "Public group description", value: settings.description || "Empty" }]} />}
    </section>
  </form>;
}
