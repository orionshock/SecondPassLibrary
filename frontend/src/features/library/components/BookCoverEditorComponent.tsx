import { useEffect, useRef, useState, type ChangeEvent, type KeyboardEvent, type MouseEvent } from "react";

import { Button } from "../../../components/ui";
import { BookCover } from "../../../shared/books/BookCover";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";

const acceptedCoverTypes = "image/jpeg,image/png,image/webp";
const previewableCoverTypes = new Set(acceptedCoverTypes.split(","));

type CoverPreviewUrlApi = Pick<typeof URL, "createObjectURL" | "revokeObjectURL">;
type CoverPreviewValidator = (url: string) => Promise<boolean>;

function browserCanDisplayImage(url: string): Promise<boolean> {
  return new Promise((resolve) => {
    const image = new Image();
    image.onload = () => resolve(true);
    image.onerror = () => resolve(false);
    image.src = url;
  });
}

export class CoverPreviewUrlOwner {
  private currentUrl?: string;

  constructor(
    private readonly urlApi: CoverPreviewUrlApi = URL,
    private readonly validate: CoverPreviewValidator = browserCanDisplayImage,
  ) {}

  async select(file: File | undefined): Promise<string | undefined> {
    this.clear();
    if (!file || !previewableCoverTypes.has(file.type.toLowerCase())) return undefined;

    const url = this.urlApi.createObjectURL(file);
    this.currentUrl = url;
    const valid = await this.validate(url);
    if (this.currentUrl !== url) return undefined;
    if (!valid) {
      this.clear();
      return undefined;
    }
    return url;
  }

  clear() {
    if (!this.currentUrl) return;
    this.urlApi.revokeObjectURL(this.currentUrl);
    this.currentUrl = undefined;
  }

  dispose() {
    this.clear();
  }
}

export function BookCoverPreviewComponent({
  coverUrl,
  previewUrl,
  title,
}: {
  coverUrl: string | null;
  previewUrl?: string;
  title: string;
}) {
  return <>
    <BookCover coverUrl={previewUrl ?? coverUrl} title={title} />
    {previewUrl ? <p className="book-cover-dialog__preview-status" role="status">Pending replacement preview</p> : null}
  </>;
}

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
  onReplace: (file: File) => Promise<boolean>;
  onClear: () => Promise<boolean>;
}) {
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<"menu" | "file" | "clear">("menu");
  const changeButton = useRef<HTMLButtonElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const previewOwner = useRef<CoverPreviewUrlOwner | null>(null);
  const [preview, setPreview] = useState<{ file: File; url: string }>();
  if (!previewOwner.current) previewOwner.current = new CoverPreviewUrlOwner();
  const controlsDisabled = disabled || state.pending;
  const error = fieldError(state.error, "cover") ?? state.error?.message;
  const previewUrl = preview && preview.file === selectedFile ? preview.url : undefined;

  useEffect(() => {
    if (open) closeButton.current?.focus();
  }, [open]);

  useEffect(() => {
    let active = true;
    setPreview(undefined);
    void previewOwner.current!.select(selectedFile).then((url) => {
      if (active && url && selectedFile) setPreview({ file: selectedFile, url });
    });
    return () => { active = false; };
  }, [selectedFile]);

  useEffect(() => () => previewOwner.current?.dispose(), []);

  function selectFile(event: ChangeEvent<HTMLInputElement>) {
    onFileChange(event.currentTarget.files?.[0]);
  }

  function clearSelection() {
    if (fileInput.current) fileInput.current.value = "";
    onFileChange(undefined);
  }

  function showMode(nextMode: "menu" | "file" | "clear") {
    if (state.pending) return;
    onFileChange(undefined);
    setMode(nextMode);
  }

  async function replaceCover() {
    if (!selectedFile) return;
    if (await onReplace(selectedFile)) setMode("menu");
  }

  async function clearCover() {
    if (await onClear()) setMode("menu");
  }

  function close() {
    if (state.pending) return;
    setOpen(false);
    setMode("menu");
    onFileChange(undefined);
    changeButton.current?.focus();
  }

  function handleDialogKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      close();
    }
  }

  function handleBackdropClick(event: MouseEvent<HTMLDivElement>) {
    if (event.target === event.currentTarget) close();
  }

  return <section className="book-cover-editor" aria-label="Book cover controls">
    <Button ref={changeButton} type="button" tone="primary" className="book-cover-editor__trigger" disabled={controlsDisabled} onClick={() => { setMode("menu"); setOpen(true); }}>
      Change Cover
    </Button>
    {open ? <div className="book-cover-dialog-backdrop" onClick={handleBackdropClick}>
      <div className="book-cover-dialog" role="dialog" aria-modal="true" aria-labelledby="book-cover-dialog-title" onKeyDown={handleDialogKeyDown}>
        <header className="book-cover-dialog__header">
          <h2 id="book-cover-dialog-title">Change Cover</h2>
          <Button ref={closeButton} type="button" size="small" tone="secondary" disabled={state.pending} onClick={close}>Close</Button>
        </header>
        <div className="book-cover-dialog__body">
          <div className="book-cover-dialog__preview"><BookCoverPreviewComponent coverUrl={coverUrl} previewUrl={previewUrl} title={title} /></div>
          <div className="book-cover-dialog__controls">
            {error ? <p className="book-cover-dialog__error" role="alert">{error}</p> : null}
            {state.message ? <p className="book-cover-dialog__success" role="status">{state.message}</p> : null}
            {mode === "menu" ? <div className="book-cover-dialog__menu">
              <Button type="button" disabled={controlsDisabled} onClick={() => showMode("file")}>{coverUrl ? "Replace Cover" : "Set Cover"}</Button>
              {coverUrl ? <Button type="button" tone="danger" disabled={controlsDisabled} onClick={() => showMode("clear")}>Clear Cover</Button> : null}
            </div> : null}
            {mode === "file" ? <>
              <label className="book-cover-editor__file" htmlFor="book-edit-cover-file">
                <span>{coverUrl ? "Replacement image" : "Cover image"}</span>
                <input ref={fileInput} key={inputResetKey} id="book-edit-cover-file" type="file" accept={acceptedCoverTypes} disabled={controlsDisabled} onChange={selectFile} />
              </label>
              <div className="book-cover-editor__selection-row">
                <p className="book-cover-editor__selection">{selectedFile ? selectedFile.name : "No image selected."}</p>
                {selectedFile ? <Button type="button" size="small" tone="secondary" disabled={controlsDisabled} onClick={clearSelection}>Clear selection</Button> : null}
              </div>
              <div className="book-cover-editor__actions">
                <Button type="button" tone="secondary" disabled={state.pending} onClick={() => showMode("menu")}>Back</Button>
                <Button type="button" className="book-cover-editor__accept" disabled={controlsDisabled || !selectedFile} onClick={replaceCover}>{pendingAction === "replace" ? "Saving..." : coverUrl ? "Replace Cover" : "Set Cover"}</Button>
              </div>
            </> : null}
            {mode === "clear" ? <div className="book-cover-dialog__confirmation">
              <span>Clear the current cover?</span>
              <Button type="button" size="small" tone="secondary" disabled={controlsDisabled} onClick={() => showMode("menu")}>Back</Button>
              <Button type="button" size="small" tone="danger" disabled={controlsDisabled} onClick={clearCover}>{pendingAction === "clear" ? "Clearing..." : "Confirm Clear Cover"}</Button>
            </div> : null}
          </div>
        </div>
      </div>
    </div> : null}
  </section>;
}
