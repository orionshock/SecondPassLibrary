import type { LibraryGroupsSettings } from "@second-pass/spl-api";

import { Button } from "../../../components/UiPrimitives";
import { ActionRow } from "../../../shared/forms/ActionRow";
import type { MutationState } from "../../../shared/feedback/mutationState";

export function LibraryGroupsPageRegion({ settings, editing, state, onEnable }: {
  settings: LibraryGroupsSettings;
  editing: boolean;
  state: MutationState;
  onEnable: () => void;
}) {
  const enabled = settings.advancedGroupsEnabled;
  return <section className="server-settings-region server-settings-groups server-settings-region--centered" aria-labelledby="library-groups-heading">
    <h2 id="library-groups-heading">Advanced library groups</h2>
    <p className="muted">Create separate library spaces with their own members, curators, and shelves. Leave this off if the Public Library is all you need.</p>
    <span className={`server-settings-state server-settings-state--${enabled ? "enabled" : "disabled"}`}>{enabled ? "Enabled" : "Disabled"}</span>
    <p className="muted">{enabled
      ? "Turning this off later requires the Django Admin Service Hatch recovery flow."
      : "Enabling exposes advanced group management. Turning it off later requires the Django Admin Service Hatch recovery flow."}</p>
    {!enabled && editing ? <ActionRow state={state}><Button type="button" disabled={state.pending} onClick={onEnable}>{state.pending ? "Enabling..." : "Enable Advanced Groups"}</Button></ActionRow> : null}
  </section>;
}
