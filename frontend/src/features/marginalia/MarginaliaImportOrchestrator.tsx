import { applyMarginaliaImport, downloadUnmatchedMarginaliaImport, previewMarginaliaImport, type MarginaliaImportApplyResult, type MarginaliaImportPreview } from "@second-pass/spl-api";
import { useRef, useState, type FormEvent } from "react";

import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { idleMutationState, LocalValidationError, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import { saveDownloadedFile } from "../../shared/browser/saveDownloadedFile";
import { createMarginaliaImportDraft, buildMarginaliaImportApplyInput, marginaliaImportSelectedCount, withMarginaliaImportBookSelection, type MarginaliaImportDraft, type MarginaliaImportSessionDraft } from "./marginaliaImportDraft";
import { marginaliaImportBreadcrumbFallback } from "./marginaliaBreadcrumbs";
import { MarginaliaSectionActions } from "./components/MarginaliaSectionActions";
import { MarginaliaImportPageRegion } from "./regions/MarginaliaImportPageRegion";

export function MarginaliaImportOrchestrator() {
  usePageBreadcrumbs(marginaliaImportBreadcrumbFallback);
  const [file, setFile] = useState<File>();
  const [includeEmptySessions, setIncludeEmptySessions] = useState(false);
  const [preview, setPreview] = useState<MarginaliaImportPreview>();
  const [draft, setDraft] = useState<MarginaliaImportDraft>({});
  const [result, setResult] = useState<MarginaliaImportApplyResult>();
  const [editingSessionKeys, setEditingSessionKeys] = useState<ReadonlySet<string>>(new Set());
  const [previewState, setPreviewState] = useState<MutationState>(idleMutationState);
  const [applyState, setApplyState] = useState<MutationState>(idleMutationState);
  const [downloadState, setDownloadState] = useState<MutationState>(idleMutationState);
  const inputRef = useRef<HTMLInputElement>(null);
  const requestGuardRef = useRef(new MarginaliaImportRequestGuard());

  function invalidateStage() {
    requestGuardRef.current.invalidate();
    setPreview(undefined);
    setDraft({});
    setResult(undefined);
    setEditingSessionKeys(new Set());
    setPreviewState(idleMutationState);
    setApplyState(idleMutationState);
    setDownloadState(idleMutationState);
  }

  function changeFile(nextFile?: File) {
    setFile(nextFile);
    invalidateStage();
  }

  function changeIncludeEmptySessions(include: boolean) {
    setIncludeEmptySessions(include);
    invalidateStage();
  }

  async function submitPreview(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const requestVersion = requestGuardRef.current.begin();
    setPreviewState({ pending: true });
    try {
      const nextPreview = await previewSelectedMarginaliaImport(
        file,
        includeEmptySessions,
      );
      if (!requestGuardRef.current.accepts(requestVersion)) return;
      setPreview(nextPreview);
      setDraft(createMarginaliaImportDraft(nextPreview));
      setResult(undefined);
      setEditingSessionKeys(new Set());
      setApplyState(idleMutationState);
      setDownloadState(idleMutationState);
      setPreviewState({ pending: false, message: "Preview ready." });
    } catch (error: unknown) {
      if (!requestGuardRef.current.accepts(requestVersion)) return;
      setPreviewState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function applyImport() {
    if (!preview || marginaliaImportSelectedCount(draft) === 0) return;
    const requestVersion = requestGuardRef.current.current();
    setApplyState({ pending: true });
    try {
      const imported = await applyMarginaliaImport(buildMarginaliaImportApplyInput(preview, draft));
      if (!requestGuardRef.current.accepts(requestVersion)) return;
      setResult(imported);
      setApplyState({ pending: false, message: "Marginalia imported." });
    } catch (error: unknown) {
      if (!requestGuardRef.current.accepts(requestVersion)) return;
      setApplyState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  async function downloadUnmatched() {
    if (!preview || !(result?.unmatchedDownloadAvailable || preview.unmatchedDownloadableReadingSessionCount > 0)) return;
    const requestVersion = requestGuardRef.current.current();
    setDownloadState({ pending: true });
    try {
      const download = await downloadUnmatchedMarginaliaImport(preview.importToken);
      if (!requestGuardRef.current.accepts(requestVersion)) return;
      saveDownloadedFile(download);
      setDownloadState({ pending: false, message: "Unmatched Sessions downloaded." });
    } catch (error: unknown) {
      if (!requestGuardRef.current.accepts(requestVersion)) return;
      setDownloadState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  return <ProductPageShell className="marginalia-import-shell" title="Import Marginalia" actions={<MarginaliaSectionActions activeSection="import" />}>
    <MarginaliaImportPageRegion preview={preview} draft={draft} result={result} editingSessionKeys={editingSessionKeys} previewState={previewState} applyState={applyState} downloadState={downloadState} inputRef={inputRef} includeEmptySessions={includeEmptySessions} onIncludeEmptySessionsChange={changeIncludeEmptySessions} onFileChange={changeFile} onPreview={(event) => void submitPreview(event)} onDraftChange={(key, value: MarginaliaImportSessionDraft) => setDraft((current) => ({ ...current, [key]: value }))} onBookSelectionChange={(bookCandidateId, selected) => setDraft((current) => preview ? withMarginaliaImportBookSelection(preview, current, bookCandidateId, selected) : current)} onEditingChange={(key, editing) => setEditingSessionKeys((current) => {
      const next = new Set(current);
      if (editing) next.add(key); else next.delete(key);
      return next;
    })} onDownloadUnmatched={() => void downloadUnmatched()} onApply={() => void applyImport()} />
  </ProductPageShell>;
}

export class MarginaliaImportRequestGuard {
  private version = 0;

  begin(): number {
    this.version += 1;
    return this.version;
  }

  invalidate(): void {
    this.version += 1;
  }

  current(): number {
    return this.version;
  }

  accepts(version: number): boolean {
    return version === this.version;
  }
}

export function previewSelectedMarginaliaImport(
  file: File | undefined,
  includeEmptySessions = false,
  preview: (
    file: File,
    options: { includeEmptySessions?: boolean },
  ) => Promise<MarginaliaImportPreview> = previewMarginaliaImport,
): Promise<MarginaliaImportPreview> {
  if (!file) return Promise.reject(new LocalValidationError("Choose a marginalia archive to preview.", { file: ["Choose a marginalia archive to preview."] }));
  return preview(file, { includeEmptySessions });
}
