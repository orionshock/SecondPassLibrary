import { applyReadingImport, previewReadingImport, type ReadingImportPreview, type ReadingImportResult } from "@second-pass/spl-api";
import { useRef, useState, type FormEvent } from "react";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { idleMutationState, LocalValidationError, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { createReadingImportDraft, buildReadingImportApplyInput, readingImportSelectedCount, withReadingImportBookSelection, type ReadingImportDraft, type ReadingImportSessionDraft } from "./readingImportDraft";
import { readingImportBreadcrumbFallback } from "./readingBreadcrumbs";
import { ReadingImportPageRegion } from "./regions/ReadingImportPageRegion";

export function ReadingImportOrchestrator() {
  usePageBreadcrumbs(readingImportBreadcrumbFallback);
  const [file, setFile] = useState<File>();
  const [preview, setPreview] = useState<ReadingImportPreview>();
  const [draft, setDraft] = useState<ReadingImportDraft>({});
  const [result, setResult] = useState<ReadingImportResult>();
  const [editingSessionKeys, setEditingSessionKeys] = useState<ReadonlySet<string>>(new Set());
  const [previewState, setPreviewState] = useState<MutationState>(idleMutationState);
  const [applyState, setApplyState] = useState<MutationState>(idleMutationState);
  const inputRef = useRef<HTMLInputElement>(null);

  function changeFile(nextFile?: File) {
    setFile(nextFile);
    setPreview(undefined);
    setDraft({});
    setResult(undefined);
    setEditingSessionKeys(new Set());
    setPreviewState(idleMutationState);
    setApplyState(idleMutationState);
  }

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPreviewState({ pending: true });
    try {
      const nextPreview = await previewSelectedReadingImport(file);
      setPreview(nextPreview);
      setDraft(createReadingImportDraft(nextPreview));
      setResult(undefined);
      setEditingSessionKeys(new Set());
      setApplyState(idleMutationState);
      setPreviewState({ pending: false, message: "Preview ready." });
    } catch (error: unknown) {
      setPreviewState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function applyImport() {
    if (!preview || readingImportSelectedCount(draft) === 0) return;
    setApplyState({ pending: true });
    try {
      const imported = await applyReadingImport(buildReadingImportApplyInput(preview, draft));
      setResult(imported);
      setApplyState({ pending: false, message: "Marginalia imported." });
    } catch (error: unknown) {
      setApplyState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  return <ProductPageShellComponent className="reading-import-shell" title="Import Marginalia">
    <ReadingImportPageRegion preview={preview} draft={draft} result={result} editingSessionKeys={editingSessionKeys} previewState={previewState} applyState={applyState} inputRef={inputRef} onFileChange={changeFile} onPreview={(event) => void submitPreview(event)} onDraftChange={(key, value: ReadingImportSessionDraft) => setDraft((current) => ({ ...current, [key]: value }))} onBookSelectionChange={(bookIndex, selected) => setDraft((current) => preview ? withReadingImportBookSelection(preview, current, bookIndex, selected) : current)} onEditingChange={(key, editing) => setEditingSessionKeys((current) => {
      const next = new Set(current);
      if (editing) next.add(key); else next.delete(key);
      return next;
    })} onApply={() => void applyImport()} />
  </ProductPageShellComponent>;
}

export function previewSelectedReadingImport(file: File | undefined, preview: (file: File) => Promise<ReadingImportPreview> = previewReadingImport): Promise<ReadingImportPreview> {
  if (!file) return Promise.reject(new LocalValidationError("Choose a marginalia archive to preview.", { file: ["Choose a marginalia archive to preview."] }));
  return preview(file);
}
