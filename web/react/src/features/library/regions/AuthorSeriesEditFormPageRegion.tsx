import type { FormEvent } from "react";

import { FormField } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { SaveCancelActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import type { AuthorSeriesEditDraft } from "../authorSeriesEditDraft";
import type { DuplicateAdvisoryCandidate } from "../authorSeriesDuplicateAdvisory";
import { titleKind, type LibraryEntityKind } from "../authorSeriesLifecycle";
import { AuthorSeriesNameComboboxComponent } from "../components/AuthorSeriesNameComboboxComponent";

export function AuthorSeriesEditFormPageRegion({
  kind,
  draft,
  state,
  advisory,
  onChange,
  onSubmit,
  onCancel,
}: {
  kind: LibraryEntityKind;
  draft: AuthorSeriesEditDraft;
  state: MutationState;
  advisory: {
    enabled: boolean;
    candidates: readonly DuplicateAdvisoryCandidate[];
    pending: boolean;
    error?: Error;
    onSelectCandidate: (candidate: DuplicateAdvisoryCandidate) => void;
  };
  onChange: <K extends keyof AuthorSeriesEditDraft>(field: K, value: AuthorSeriesEditDraft[K]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  const entity = titleKind(kind);
  const proseField = kind === "author" ? "biography" : "summary";
  const proseLabel = kind === "author" ? "Biography" : "Summary";
  return <form className="author-series-edit-form" autoComplete="off" onSubmit={onSubmit}>
    <FormField label="Name" htmlFor="library-entity-name" error={fieldError(state.error, "name")}>
      <AuthorSeriesNameComboboxComponent
        kind={kind}
        value={draft.name}
        enabled={advisory.enabled}
        candidates={advisory.candidates}
        pending={advisory.pending}
        error={advisory.error}
        onChange={(value) => onChange("name", value)}
        onSelectCandidate={advisory.onSelectCandidate}
      />
    </FormField>
    <FormField label="Sort name" htmlFor="library-entity-sort-name" error={fieldError(state.error, "sortName")}>
      <input id="library-entity-sort-name" value={draft.sortName} maxLength={255} autoComplete="off" onChange={(event) => onChange("sortName", event.target.value)} />
    </FormField>
    <FormField label={proseLabel} htmlFor="library-entity-prose" error={fieldError(state.error, proseField)}>
      <textarea id="library-entity-prose" value={draft.prose} autoComplete="off" onChange={(event) => onChange("prose", event.target.value)} />
    </FormField>
    <SaveCancelActionRowComponent
      state={state}
      submitLabel={`Save ${entity}`}
      pendingLabel="Saving..."
      onCancel={onCancel}
    />
  </form>;
}
