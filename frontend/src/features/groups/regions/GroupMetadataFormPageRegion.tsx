import type { FormEvent } from "react";

import { FormField } from "../../../components/UiPrimitives";
import {
  DESCRIPTIVE_PROSE_MAX_LENGTH,
  LimitedRichTextEditor,
} from "../../../components/LimitedRichTextEditor";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { SaveCancelActionRow } from "../../../shared/forms/ActionRow";
import type { GroupDraft } from "../groupDraft";

export function GroupMetadataFormPageRegion({
  mode,
  draft,
  nameEditable,
  state,
  onChange,
  onSubmit,
  onCancel,
  disabled = false,
}: {
  mode: "new" | "edit";
  draft: GroupDraft;
  nameEditable: boolean;
  state: MutationState;
  onChange: <K extends keyof GroupDraft>(field: K, value: GroupDraft[K]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
  disabled?: boolean;
}) {
  return <form className="group-metadata-form" onSubmit={onSubmit}>
    <FormField label="Name" htmlFor="group-name" error={fieldError(state.error, "name")}>
      <input
        id="group-name"
        value={draft.name}
        maxLength={255}
        disabled={disabled || !nameEditable}
        autoFocus={nameEditable}
        onChange={(event) => onChange("name", event.target.value)}
      />
    </FormField>
    <FormField label="Description" htmlFor="group-description" error={fieldError(state.error, "description")}>
      <LimitedRichTextEditor
        id="group-description"
        value={draft.description}
        disabled={disabled}
        maxLength={DESCRIPTIVE_PROSE_MAX_LENGTH}
        onChange={(value) => onChange("description", value)}
      />
    </FormField>
    <SaveCancelActionRow
      state={state}
      submitLabel={mode === "new" ? "Create Group" : "Save Group"}
      pendingLabel="Saving..."
      disabled={disabled}
      onCancel={onCancel}
    />
  </form>;
}
