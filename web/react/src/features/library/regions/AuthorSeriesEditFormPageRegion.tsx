import type { FormEvent } from "react";

import { FormField } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { SaveCancelActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import type { AuthorSeriesEditDraft } from "../authorSeriesEditDraft";
import { titleKind, type LibraryEntityKind } from "../authorSeriesLifecycle";

export function AuthorSeriesEditFormPageRegion({
  kind,
  draft,
  state,
  onChange,
  onSubmit,
  onCancel,
}: {
  kind: LibraryEntityKind;
  draft: AuthorSeriesEditDraft;
  state: MutationState;
  onChange: <K extends keyof AuthorSeriesEditDraft>(field: K, value: AuthorSeriesEditDraft[K]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
}) {
  const entity = titleKind(kind);
  const proseField = kind === "author" ? "biography" : "summary";
  const proseLabel = kind === "author" ? "Biography" : "Summary";
  return <form className="author-series-edit-form" onSubmit={onSubmit}>
    <FormField label="Name" htmlFor="library-entity-name" error={fieldError(state.error, "name")}>
      <input id="library-entity-name" value={draft.name} maxLength={255} onChange={(event) => onChange("name", event.target.value)} autoFocus />
    </FormField>
    <FormField label="Sort name" htmlFor="library-entity-sort-name" error={fieldError(state.error, "sortName")}>
      <input id="library-entity-sort-name" value={draft.sortName} maxLength={255} onChange={(event) => onChange("sortName", event.target.value)} />
    </FormField>
    <FormField label={proseLabel} htmlFor="library-entity-prose" error={fieldError(state.error, proseField)}>
      <textarea id="library-entity-prose" value={draft.prose} onChange={(event) => onChange("prose", event.target.value)} />
    </FormField>
    <SaveCancelActionRowComponent
      state={state}
      submitLabel={`Save ${entity}`}
      pendingLabel="Saving..."
      onCancel={onCancel}
    />
  </form>;
}
