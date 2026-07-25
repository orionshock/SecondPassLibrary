import type { ChangeEvent } from "react";

import { Button } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { confirmBookCoverClear } from "../bookCoverMutation";

const acceptedCoverTypes = "image/jpeg,image/png,image/webp";

export function BookCoverEditorComponent({
  coverUrl,
  selectedFile,
  inputResetKey,
  state,
  pendingAction,
  disabled = false,
  onFileChange,
  onReplace,
  onClear,
}: {
  coverUrl: string | null;
  selectedFile?: File;
  inputResetKey: number;
  state: MutationState;
  pendingAction?: "replace" | "clear";
  disabled?: boolean;
  onFileChange: (file: File | undefined) => void;
  onReplace: (file: File) => void;
  onClear: () => void;
}) {
  const controlsDisabled = disabled || state.pending;
  const error = fieldError(state.error, "cover") ?? state.error?.message;

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.currentTarget.files?.[0]);
  }

  function clearCover() {
    if (confirmBookCoverClear()) onClear();
  }

  return <section className="book-cover-editor" aria-label="Book cover">
    <label className="book-cover-editor__file" htmlFor="book-edit-cover-file">
      <span>Replacement image</span>
      <input
        key={inputResetKey}
        id="book-edit-cover-file"
        type="file"
        accept={acceptedCoverTypes}
        disabled={controlsDisabled}
        onChange={selectFile}
      />
    </label>
    <p className="book-cover-editor__selection">
      {selectedFile ? selectedFile.name : "No image selected."}
    </p>
    <div className="book-cover-editor__actions">
      <Button
        type="button"
        disabled={controlsDisabled || !selectedFile}
        onClick={() => selectedFile && onReplace(selectedFile)}
      >{pendingAction === "replace" ? "Replacing..." : "Replace cover"}</Button>
      {coverUrl ? <Button
        type="button"
        className="button--secondary"
        disabled={controlsDisabled}
        onClick={clearCover}
      >{pendingAction === "clear" ? "Clearing..." : "Clear cover"}</Button> : null}
    </div>
    <div className="book-cover-editor__feedback" aria-live="polite">
      {error ? <p role="alert">{error}</p> : state.message ? <p>{state.message}</p> : null}
    </div>
  </section>;
}
