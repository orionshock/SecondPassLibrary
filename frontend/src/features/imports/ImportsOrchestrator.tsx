import { canSeeImports, uploadLibraryImport, type LibraryImportResult } from "@second-pass/spl-api";
import { useRef, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel } from "../../components/ui";
import { idleMutationState, LocalValidationError, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import type { ImportResultBookNavigation } from "./components/ImportResultItem";
import { ImportResultPageRegion } from "./regions/ImportResultPageRegion";
import { ImportUploadPageRegion } from "./regions/ImportUploadPageRegion";
import "./Imports.css";

export const importsBreadcrumbFallback = [] as const;

export function importResultBookNavigation(bookId: string, title: string): ImportResultBookNavigation {
  return {
    to: `/library/books/${encodeURIComponent(bookId)}`,
    state: breadcrumbNavigationState([
      { label: "Book Import", to: "/imports", resetTrail: true, icon: "import" },
      { label: title, icon: "book" },
    ]),
  };
}

export function ImportsOrchestrator() {
  usePageBreadcrumbs(importsBreadcrumbFallback);
  const { currentUser } = useOutletContext<AppOutletContext>();
  const [file, setFile] = useState<File>();
  const [state, setState] = useState<MutationState>(idleMutationState);
  const [result, setResult] = useState<LibraryImportResult>();
  const inputRef = useRef<HTMLInputElement>(null);

  if (!canSeeImports(currentUser)) return <div className="imports-state"><ErrorPanel>You do not have permission to import library files.</ErrorPanel></div>;

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

  return <ProductPageShell className="imports-page" title="Imports">
    <ImportUploadPageRegion state={state} inputRef={inputRef} onFileChange={(value) => { setFile(value); setState(idleMutationState); }} onSubmit={(event) => void submit(event)} />
    <ImportResultPageRegion result={result} bookNavigation={importResultBookNavigation} />
  </ProductPageShell>;
}

export function uploadSelectedLibraryFile(
  file: File | undefined,
  upload: (file: File) => Promise<LibraryImportResult> = uploadLibraryImport,
): Promise<LibraryImportResult> {
  if (!file) return Promise.reject(new LocalValidationError("Choose a file to import.", { file: ["Choose a file to import."] }));
  return upload(file);
}

export function clearImportFileInput(input: Pick<HTMLInputElement, "value"> | null): void {
  if (input) input.value = "";
}
