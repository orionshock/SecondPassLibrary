import { applyReadingImport, downloadUnmatchedReadingImport, previewReadingImport, type ReadingImportPreview, type ReadingImportResult } from "@second-pass/spl-api";
import { useRef, useState, type FormEvent } from "react";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { idleMutationState, LocalValidationError, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import { saveDownloadedFile } from "../../shared/browser/saveDownloadedFile";
import { createMarginaliaImportDraft, buildMarginaliaImportApplyInput, marginaliaImportSelectedCount, withMarginaliaImportBookSelection, type MarginaliaImportDraft, type MarginaliaImportSessionDraft } from "./marginaliaImportDraft";
import { marginaliaImportBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { MarginaliaSectionActionsComponent } from "./components/MarginaliaSectionActionsComponent";
import { MarginaliaImportPageRegion } from "./regions/MarginaliaImportPageRegion";

export function MarginaliaImportOrchestrator() {
  usePageBreadcrumbs(marginaliaImportBreadcrumbFallback);
  const [file, setFile] = useState<File>();
  const [includeEmptySessions, setIncludeEmptySessions] = useState(false);
  const [preview, setPreview] = useState<ReadingImportPreview>();
  const [draft, setDraft] = useState<MarginaliaImportDraft>({});
  const [result, setResult] = useState<ReadingImportResult>();
  const [editingSessionKeys, setEditingSessionKeys] = useState<ReadonlySet<string>>(new Set());
  const [previewState, setPreviewState] = useState<MutationState>(idleMutationState);
  const [applyState, setApplyState] = useState<MutationState>(idleMutationState);
  const [downloadState, setDownloadState] = useState<MutationState>(idleMutationState);
  const inputRef = useRef<HTMLInputElement>(null);

  function changeFile(nextFile?: File) {
    setFile(nextFile);
    setPreview(undefined);
    setDraft({});
    setResult(undefined);
    setEditingSessionKeys(new Set());
    setPreviewState(idleMutationState);
    setApplyState(idleMutationState);
    setDownloadState(idleMutationState);
  }

  function changeIncludeEmptySessions(include: boolean) {
    setIncludeEmptySessions(include);
    setPreview(undefined);
    setDraft({});
    setResult(undefined);
    setEditingSessionKeys(new Set());
    setPreviewState(idleMutationState);
    setApplyState(idleMutationState);
    setDownloadState(idleMutationState);
  }

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPreviewState({ pending: true });
    try {
      const nextPreview = await previewSelectedMarginaliaImport(
        file,
        includeEmptySessions,
      );
      setPreview(nextPreview);
      setDraft(createMarginaliaImportDraft(nextPreview));
      setResult(undefined);
      setEditingSessionKeys(new Set());
      setApplyState(idleMutationState);
      setDownloadState(idleMutationState);
      setPreviewState({ pending: false, message: "Preview ready." });
    } catch (error: unknown) {
      setPreviewState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function applyImport() {
    if (!preview || marginaliaImportSelectedCount(draft) === 0) return;
    setApplyState({ pending: true });
    try {
      const imported = await applyReadingImport(buildMarginaliaImportApplyInput(preview, draft));
      setResult(imported);
      setApplyState({ pending: false, message: "Marginalia imported." });
    } catch (error: unknown) {
      setApplyState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function downloadUnmatched() {
    if (!preview || preview.unmatchedDownloadableSessionCount === 0) return;
    setDownloadState({ pending: true });
    try {
      saveDownloadedFile(await downloadUnmatchedReadingImport(preview.importToken));
      setDownloadState({ pending: false, message: "Unmatched Sessions downloaded." });
    } catch (error: unknown) {
      setDownloadState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  return <ProductPageShellComponent className="marginalia-import-shell" title="Import Marginalia" actions={<MarginaliaSectionActionsComponent activeSection="import" />}>
    <MarginaliaImportPageRegion preview={preview} draft={draft} result={result} editingSessionKeys={editingSessionKeys} previewState={previewState} applyState={applyState} downloadState={downloadState} inputRef={inputRef} includeEmptySessions={includeEmptySessions} onIncludeEmptySessionsChange={changeIncludeEmptySessions} onFileChange={changeFile} onPreview={(event) => void submitPreview(event)} onDraftChange={(key, value: MarginaliaImportSessionDraft) => setDraft((current) => ({ ...current, [key]: value }))} onBookSelectionChange={(bookIndex, selected) => setDraft((current) => preview ? withMarginaliaImportBookSelection(preview, current, bookIndex, selected) : current)} onEditingChange={(key, editing) => setEditingSessionKeys((current) => {
      const next = new Set(current);
      if (editing) next.add(key); else next.delete(key);
      return next;
    })} onDownloadUnmatched={() => void downloadUnmatched()} onApply={() => void applyImport()} />
  </ProductPageShellComponent>;
}

export function previewSelectedMarginaliaImport(
  file: File | undefined,
  includeEmptySessions = false,
  preview: (
    file: File,
    options: { includeEmptySessions?: boolean },
  ) => Promise<ReadingImportPreview> = previewReadingImport,
): Promise<ReadingImportPreview> {
  if (!file) return Promise.reject(new LocalValidationError("Choose a marginalia archive to preview.", { file: ["Choose a marginalia archive to preview."] }));
  return preview(file, { includeEmptySessions });
}
