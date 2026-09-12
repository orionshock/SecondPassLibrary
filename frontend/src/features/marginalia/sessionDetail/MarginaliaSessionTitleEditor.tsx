import type { KeyboardEvent, ReactNode } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { IconButton } from "../../../components/UiPrimitives";

export function MarginaliaSessionTitleEditor({
  displayName,
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
  displayName: string;
  editable: boolean;
  draft: string;
  editing: boolean;
  pending: boolean;
  feedback?: ReactNode;
  onDraftChange: (name: string) => void;
  onEdit: () => void;
  onSave: () => void;
  onCancel: () => void;
}) {
  const isEditing = editable && editing;

  function handleKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (pending) return;
    if (event.key === "Enter") {
      event.preventDefault();
      onSave();
    } else if (event.key === "Escape") {
      event.preventDefault();
      onCancel();
    }
  }

  return <span className="page-header__title-content marginalia-session-title-editor">
    {isEditing
      ? <input
          className="marginalia-session-title-editor__input"
          aria-label="Reading Session name"
          autoFocus
          maxLength={255}
          value={draft}
          disabled={pending}
          onChange={(event) => onDraftChange(event.target.value)}
          onKeyDown={handleKeyDown}
        />
      : <span>{displayName}</span>}
    {isEditing ? <>
      <IconButton className="marginalia-inline-edit-button" type="button" aria-label="Save Reading Session name" title="Save Reading Session name" disabled={pending} onClick={onSave}><MaterialIcon name="check" /></IconButton>
      <IconButton className="marginalia-inline-edit-button" type="button" aria-label="Cancel editing Reading Session name" title="Cancel editing Reading Session name" disabled={pending} onClick={onCancel}><MaterialIcon name="close" /></IconButton>
    </> : editable ? <IconButton className="marginalia-inline-edit-button" type="button" aria-label="Edit Reading Session name" title="Edit Reading Session name" disabled={pending} onClick={onEdit}><MaterialIcon name="edit" /></IconButton> : null}
    {feedback ? <span className="marginalia-inline-editor-feedback">{feedback}</span> : null}
  </span>;
}
