import { type FormEvent, type RefObject } from "react";

import { Button, FormField, Surface } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRow } from "../../../shared/forms/ActionRow";

export function ImportUploadPageRegion({ state, inputRef, onFileChange, onSubmit }: {
  state: MutationState;
  inputRef: RefObject<HTMLInputElement | null>;
  onFileChange: (file?: File) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <Surface title="Upload">
    <form className="imports-upload-form" encType="multipart/form-data" onSubmit={onSubmit}>
      <p className="muted">Import one EPUB or a ZIP containing EPUB files. PDF is not supported.</p>
      <FormField label="File" htmlFor="library-import-file" error={fieldError(state.error, "file")}>
        <input ref={inputRef} id="library-import-file" name="file" type="file" accept=".epub,.zip" disabled={state.pending} onChange={(event) => onFileChange(event.target.files?.[0])} />
      </FormField>
      <ActionRow state={state}><Button type="submit" disabled={state.pending}>{state.pending ? "Importing..." : "Import"}</Button></ActionRow>
    </form>
  </Surface>;
}
