import { ApiError, uploadLibraryImport, type LibraryImportResult } from "@second-pass/spl-api";
import { useRef, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel, PageHeader } from "../../components/ui";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ImportResultPageRegion } from "./regions/ImportResultPageRegion";
import { ImportUploadPageRegion } from "./regions/ImportUploadPageRegion";
import "./Imports.css";

export const importsBreadcrumbFallback = [] as const;

export function ImportsOrchestrator() {
  usePageBreadcrumbs(importsBreadcrumbFallback);
  const { currentUser } = useOutletContext<AppOutletContext>();
  const [file, setFile] = useState<File>();
  const [state, setState] = useState<MutationState>(idleMutationState);
  const [result, setResult] = useState<LibraryImportResult>();
  const inputRef = useRef<HTMLInputElement>(null);

  if (!canAccessLibraryImports(currentUser)) return <div className="imports-state"><ErrorPanel>You do not have permission to import library files.</ErrorPanel></div>;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setState({ pending: true });
    try {
      const imported = await uploadSelectedLibraryFile(file);
      setResult(imported);
      setFile(undefined);
      clearImportFileInput(inputRef.current);
      setState({ pending: false, message: "Import complete." });
    } catch (error: unknown) {
      setState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  return <div className="page-stack imports-page">
    <PageHeader title="Imports" />
    <ImportUploadPageRegion state={state} inputRef={inputRef} onFileChange={(value) => { setFile(value); setState(idleMutationState); }} onSubmit={(event) => void submit(event)} />
    <ImportResultPageRegion result={result} />
  </div>;
}

export function canAccessLibraryImports(user: { isOwner: boolean; role: string }): boolean {
  return user.isOwner || user.role === "manager" || user.role === "librarian";
}

export function uploadSelectedLibraryFile(
  file: File | undefined,
  upload: (file: File) => Promise<LibraryImportResult> = uploadLibraryImport,
): Promise<LibraryImportResult> {
  if (!file) return Promise.reject(new ApiError("Choose a file to import.", 400, { fields: { file: ["Choose a file to import."] } }));
  return upload(file);
}

export function clearImportFileInput(input: Pick<HTMLInputElement, "value"> | null): void {
  if (input) input.value = "";
}
