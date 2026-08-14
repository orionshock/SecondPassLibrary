import type { LibraryGroup, ShelfSummary } from "@second-pass/spl-api";
import type { FormEvent } from "react";

import { Button, ErrorPanel, FormField } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { SaveCancelActionRow } from "../../../shared/forms/ActionRow";
import { GroupBadge } from "../../../shared/groups/GroupBadge";
import type { ShelfDraft } from "../shelfDraft";
import type { ShelfLifecycleMode } from "../shelfLifecycle";

export function ShelfDetailsEditPageRegion({
  mode,
  shelf,
  draft,
  groups,
  groupsLoading,
  groupsError,
  mutation,
  deleteMutation,
  itemMutationPending,
  onChange,
  onOwnerTypeChange,
  onSubmit,
  onCancel,
  onDelete,
}: {
  mode: ShelfLifecycleMode;
  shelf?: ShelfSummary;
  draft: ShelfDraft;
  groups: readonly LibraryGroup[];
  groupsLoading: boolean;
  groupsError?: Error;
  mutation: MutationState;
  deleteMutation: MutationState;
  itemMutationPending?: boolean;
  onChange: <K extends keyof ShelfDraft>(field: K, value: ShelfDraft[K]) => void;
  onOwnerTypeChange: (ownerType: ShelfDraft["ownerType"]) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onCancel: () => void;
  onDelete: () => void;
}) {
  const canChooseGroupOwner = mode === "new" && groups.length > 0;
  return <div className="shelf-lifecycle-surface">
    <form className="shelf-lifecycle-form" onSubmit={onSubmit}>
      {mode === "new" && canChooseGroupOwner ? <FormField label="Owner" htmlFor="shelf-owner-type" error={fieldError(mutation.error, "ownerType")}>
        <select id="shelf-owner-type" value={draft.ownerType} onChange={(event) => onOwnerTypeChange(event.target.value as ShelfDraft["ownerType"])}>
          <option value="user">Personal</option>
          <option value="group">Library Group</option>
        </select>
      </FormField> : null}
      {mode === "new" && draft.ownerType === "group" ? <FormField label="Library Group" htmlFor="shelf-owner-group" error={fieldError(mutation.error, "ownerGroupId")}>
        <select id="shelf-owner-group" value={draft.ownerGroupId} onChange={(event) => onChange("ownerGroupId", event.target.value)}>
          <option value="">Choose a group</option>
          {groups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
        </select>
      </FormField> : null}
      {mode === "edit" && shelf?.ownerType === "group" ? <div className="shelf-lifecycle-owner-context">
        <span>Owned by</span>
        <GroupBadge name={shelf.ownerGroup?.name ?? "Library Group"} isPublicGroup={shelf.ownerGroup?.isPublicGroup} />
      </div> : null}
      {mode === "new" && groupsLoading ? <p className="muted shelf-group-picker-note" aria-live="polite">Loading group choices...</p> : null}
      {mode === "new" && groupsError ? <div className="shelf-group-picker-error"><ErrorPanel>{groupsError.message}</ErrorPanel><p className="muted">You can still create a personal shelf.</p></div> : null}
      <FormField label="Name" htmlFor="shelf-name" error={fieldError(mutation.error, "name")}>
        <input id="shelf-name" value={draft.name} maxLength={255} autoFocus onChange={(event) => onChange("name", event.target.value)} />
      </FormField>
      <FormField label="Description" htmlFor="shelf-description" error={fieldError(mutation.error, "description")}>
        <textarea id="shelf-description" value={draft.description} onChange={(event) => onChange("description", event.target.value)} />
      </FormField>
      {draft.ownerType === "user" ? <FormField label="Visibility" htmlFor="shelf-visibility" error={fieldError(mutation.error, "visibility")}>
        <select id="shelf-visibility" value={draft.visibility} onChange={(event) => onChange("visibility", event.target.value as ShelfDraft["visibility"])}>
          <option value="private">Private</option>
          <option value="listed">Listed</option>
        </select>
      </FormField> : null}
      <SaveCancelActionRow
        state={mutation}
        submitLabel={mode === "new" ? "Create Shelf" : "Save Shelf"}
        pendingLabel="Saving..."
        disabled={deleteMutation.pending || itemMutationPending}
        onCancel={onCancel}
      />
    </form>
    {mode === "edit" ? <section className="shelf-danger-zone" aria-labelledby="shelf-delete-heading">
      <div>
        <h2 id="shelf-delete-heading">Delete Shelf</h2>
        <p>Deletes this shelf and its shelf items. Books and files are not deleted.</p>
        {deleteMutation.error ? <ErrorPanel>{deleteMutation.error.message}</ErrorPanel> : null}
      </div>
      <Button type="button" tone="danger" disabled={mutation.pending || deleteMutation.pending} onClick={onDelete}>
        {deleteMutation.pending ? "Deleting..." : "Delete Shelf"}
      </Button>
    </section> : null}
  </div>;
}
