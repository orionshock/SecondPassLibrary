import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent } from "react";

import { Button } from "../../../components/ui";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

const acceptedCoverTypes = "image/jpeg,image/png,image/webp";

export function BookCoverEditorComponent({
  coverUrl,
  title,
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
  title: string;
  selectedFile?: File;
  inputResetKey: number;
  state: MutationState;
  pendingAction?: "replace" | "clear";
  disabled?: boolean;
  onFileChange: (file: File | undefined) => void;
  onReplace: (file: File) => void;
  onClear: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirmingClear, setConfirmingClear] = useState(false);
  const changeButton = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const controlsDisabled = disabled || state.pending;
  const error = fieldError(state.error, "cover") ?? state.error?.message;

  useEffect(() => {
    if (open) closeButton.current?.focus();
  }, [open]);

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.currentTarget.files?.[0]);
  }

  function close() {
    if (state.pending) return;
    setOpen(false);
    setConfirmingClear(false);
    onFileChange(undefined);
    changeButton.current?.focus();
  }

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  }

  return <section className="book-cover-editor" aria-label="Book cover controls">
    <Button ref={changeButton} type="button" tone="secondary" className="book-cover-editor__trigger" disabled={controlsDisabled} onClick={() => setOpen(true)}>
      Change Cover
    </Button>
    {open ? <div className="book-cover-dialog-backdrop">
      <div className="book-cover-dialog" role="dialog" aria-modal="true" aria-labelledby="book-cover-dialog-title" onKeyDown={handleDialogKeyDown}>
        <header className="book-cover-dialog__header">
          <h2 id="book-cover-dialog-title">Change Cover</h2>
          <Button ref={closeButton} type="button" tone="secondary" disabled={state.pending} onClick={close}>Close</Button>
        </header>
        <div className="book-cover-dialog__body">
          <div className="book-cover-dialog__preview"><BookCoverComponent coverUrl={coverUrl} title={title} /></div>
          <div className="book-cover-dialog__controls">
            <label className="book-cover-editor__file" htmlFor="book-edit-cover-file">
              <span>Replacement image</span>
              <input key={inputResetKey} id="book-edit-cover-file" type="file" accept={acceptedCoverTypes} disabled={controlsDisabled} onChange={selectFile} />
            </label>
            <p className="book-cover-editor__selection">{selectedFile ? selectedFile.name : "No image selected."}</p>
            {error ? <p className="book-cover-dialog__error" role="alert">{error}</p> : null}
            {state.message ? <p className="book-cover-dialog__success" role="status">{state.message}</p> : null}
            {confirmingClear ? <div className="book-cover-dialog__confirmation">
              <span>Clear the current cover?</span>
              <Button type="button" tone="danger" disabled={controlsDisabled} onClick={onClear}>{pendingAction === "clear" ? "Clearing..." : "Confirm Clear Cover"}</Button>
              <Button type="button" tone="secondary" disabled={controlsDisabled} onClick={() => setConfirmingClear(false)}>Keep Cover</Button>
            </div> : <div className="book-cover-editor__actions">
              <Button type="button" disabled={controlsDisabled || !selectedFile} onClick={() => selectedFile && onReplace(selectedFile)}>{pendingAction === "replace" ? "Replacing..." : "Replace Cover"}</Button>
              {coverUrl ? <Button type="button" tone="secondary" disabled={controlsDisabled} onClick={() => setConfirmingClear(true)}>Clear Cover</Button> : null}
              <Button type="button" tone="secondary" disabled={state.pending} onClick={close}>Cancel</Button>
            </div>}
          </div>
        </div>
      </div>
    </div> : null}
  </section>;
}
