import type { KeyboardEvent, ReactNode } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { IconButton } from "../../../components/ui";

export function MarginaliaSessionNoteEditorComponent({
  note,
  editable,
  draft,
  editing,
  pending,
  feedback,
  onDraftChange,
  onEdit,
  onSave,
  onCancel,
}: {
  note: string;
  editable: boolean;
  draft: string;
  editing: boolean;
  pending: boolean;
  feedback?: ReactNode;
  onDraftChange: (note: string) => void;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const isEditing = editable && editing;

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (pending) return;
    if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      onSave();
    }
  }

  return <div className="marginalia-session-detail__notes">
    <div className="marginalia-session-detail__notes-heading">
      <strong>Session Note</strong>
      {isEditing ? <span className="marginalia-inline-editor-actions">
        <IconButton className="marginalia-inline-edit-button" type="button" aria-label="Save session note" title="Save session note" disabled={pending} onClick={onSave}><MaterialIcon name="check" /></IconButton>
        <IconButton className="marginalia-inline-edit-button" type="button" aria-label="Cancel editing session note" title="Cancel editing session note" disabled={pending} onClick={onCancel}><MaterialIcon name="close" /></IconButton>
      </span> : editable ? <IconButton className="marginalia-inline-edit-button" type="button" aria-label="Edit session note" title="Edit session note" disabled={pending} onClick={onEdit}><MaterialIcon name="edit" /></IconButton> : null}
      {feedback ? <span className="marginalia-inline-editor-feedback">{feedback}</span> : null}
    </div>
    {isEditing
      ? <textarea aria-label="Session Note" value={draft} disabled={pending} onChange={(event) => onDraftChange(event.target.value)} onKeyDown={handleKeyDown} />
      : note.trim() ? <p>{note}</p> : null}
  </div>;
}
