import type { ReadingImportPreview, ReadingImportResult } from "@second-pass/spl-api";
import { useEffect, useRef, type FormEvent, type RefObject } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, FormField, Surface } from "../../../components/ui";
import { HelpPopoverComponent } from "../../../components/HelpPopoverComponent";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import { marginaliaImportBookSelectionState, marginaliaImportSelectedCount, marginaliaImportSessionKey, type MarginaliaImportBookSelectionState, type MarginaliaImportDraft, type MarginaliaImportSessionDraft } from "../marginaliaImportDraft";

export function MarginaliaImportPageRegion({ preview, draft, result, editingSessionKeys, previewState, applyState, inputRef, onFileChange, onPreview, onDraftChange, onBookSelectionChange, onEditingChange, onApply }: {
  preview?: ReadingImportPreview;
  draft: MarginaliaImportDraft;
  editingSessionKeys: ReadonlySet<string>;
  result?: ReadingImportResult;
  previewState: MutationState;
  applyState: MutationState;
  inputRef: RefObject<HTMLInputElement | null>;
  onFileChange: (file?: File) => void;
  onPreview: (event: FormEvent<HTMLFormElement>) => void;
  onDraftChange: (key: string, value: MarginaliaImportSessionDraft) => void;
  onBookSelectionChange: (bookIndex: number, selected: boolean) => void;
  onEditingChange: (key: string, editing: boolean) => void;
  onApply: () => void;
}) {
  const selectedCount = marginaliaImportSelectedCount(draft);
  return <div className="marginalia-import-page">
    <Surface title="Upload">
      <form className="marginalia-import-upload" encType="multipart/form-data" onSubmit={onPreview}>
        <p className="muted">Choose a native Second Pass marginalia JSON archive. Nothing changes until Apply.</p>
        <div className="marginalia-import-upload__file-row">
          <FormField label="Marginalia archive" htmlFor="marginalia-import-file" error={fieldError(previewState.error, "file")}>
            <input ref={inputRef} id="marginalia-import-file" name="file" type="file" accept=".json,application/json" disabled={previewState.pending || applyState.pending} onChange={(event) => onFileChange(event.target.files?.[0])} />
          </FormField>
          <ActionRowComponent state={previewState}><Button type="submit" disabled={previewState.pending || applyState.pending}>{previewState.pending ? "Previewing..." : "Preview"}</Button></ActionRowComponent>
        </div>
      </form>
    </Surface>
    {preview && !result ? <MarginaliaImportReview preview={preview} draft={draft} editingSessionKeys={editingSessionKeys} selectedCount={selectedCount} applyState={applyState} onDraftChange={onDraftChange} onBookSelectionChange={onBookSelectionChange} onEditingChange={onEditingChange} onApply={onApply} /> : null}
    {result ? <MarginaliaImportResultRegion result={result} /> : null}
  </div>;
}

function MarginaliaImportReview({ preview, draft, editingSessionKeys, selectedCount, applyState, onDraftChange, onBookSelectionChange, onEditingChange, onApply }: {
  preview: ReadingImportPreview;
  draft: MarginaliaImportDraft;
  editingSessionKeys: ReadonlySet<string>;
  selectedCount: number;
  applyState: MutationState;
  onDraftChange: (key: string, value: MarginaliaImportSessionDraft) => void;
  onBookSelectionChange: (bookIndex: number, selected: boolean) => void;
  onEditingChange: (key: string, editing: boolean) => void;
  onApply: () => void;
}) {
  const summaryWarnings = preview.warnings.filter((warning) => !/(?:reader-assisted import|second pass reader import)/i.test(warning));
  const unmatchedSessionCount = preview.books.reduce((count, book) => count + (book.matchStatus === "unmatched" ? book.sessionCount : book.sessions.filter((session) => session.needsReader).length), 0);
  if (preview.unmatchedEntries) {
    summaryWarnings.unshift(`${preview.unmatchedEntries} exported Book ${preview.unmatchedEntries === 1 ? "entry did" : "entries did"} not match a visible local Book and ${preview.unmatchedEntries === 1 ? "requires" : "require"} Second Pass Reader Import.`);
  }

  return <section className="marginalia-import-review" aria-labelledby="marginalia-import-review-heading">
    <header className="marginalia-import-review__header">
      <h2 id="marginalia-import-review-heading">Review</h2>
      <div className="marginalia-import-summary" aria-label="Import preview summary">
        <Badge>{preview.summary.books} books</Badge><Badge>{preview.summary.sessions} sessions</Badge><Badge>{preview.summary.annotations} annotations</Badge>
      </div>
    </header>
    {summaryWarnings.length ? <div className="marginalia-import-summary__warnings">{summaryWarnings.map((warning, index) => <span className="marginalia-import-summary__warning" key={index}><span className="css-dot" aria-hidden="true" />{warning}</span>)}</div> : null}
    <div className="marginalia-import-books">
      {preview.books.map((book, bookIndex) => <section className="marginalia-import-book" key={bookIndex}>
        <div className="marginalia-import-book__cover">
          <BookCoverComponent coverUrl={book.coverUrl} title={book.title || "Imported Book"} />
        </div>
        <div className="marginalia-import-book__content">
          <header className="marginalia-import-book__header">
            <div className="marginalia-import-book__identity">
              {book.matchStatus === "matched" && book.sessions.some((session) => session.willImport) ? <BookSelectionCheckbox label={book.title || "Untitled Book"} state={marginaliaImportBookSelectionState(preview, draft, bookIndex)} disabled={applyState.pending} onChange={(selected) => onBookSelectionChange(bookIndex, selected)} /> : null}
              <h2>{book.title || "Untitled Book"}</h2>{book.authors.length ? <><span className="css-dot" aria-hidden="true" /><span className="marginalia-import-book__authors">{book.authors.join(", ")}</span></> : null}
            </div>
            <span className="marginalia-import-book__match">
              {book.matchStatus === "matched"
                ? <Badge tone="success">Matched</Badge>
                : book.warning
                  ? <HelpPopoverComponent ariaLabel={`Why ${book.title || "this Book"} is unmatched`} icon="warning_amber" label="Unmatched" mouseoverText={book.warning} border borderColor="#d8b65a" color="#d8b65a" />
                  : <Badge>Unmatched</Badge>}
            </span>
          </header>
          {book.matchStatus === "matched" && book.warning ? <p className="marginalia-import-warning">{book.warning}</p> : null}
          <div className="marginalia-import-sessions">{book.sessions.map((session, sessionIndex) => {
          const key = marginaliaImportSessionKey(bookIndex, sessionIndex);
          const value = draft[key] ?? { selected: false, name: session.name, notes: session.notes };
          const editing = editingSessionKeys.has(key);
          const sessionIdentity = <><span>{value.name.trim() || "Unnamed session"}</span><span className="css-dot" aria-hidden="true" /><span className="marginalia-import-session__annotation-count">{session.annotationCount} annotations</span></>;
          return <article className="marginalia-import-session" key={key}>
            <div className="marginalia-import-session__summary">
              <div>
                {session.willImport ? <label className="marginalia-import-session__select">
                  <input type="checkbox" checked={value.selected} disabled={applyState.pending} onChange={(event) => onDraftChange(key, { ...value, selected: event.target.checked })} />
                  {sessionIdentity}
                </label> : <div className="marginalia-import-session__select">{sessionIdentity}</div>}
                {session.activeWillImportAsHistorical ? <div className="marginalia-import-session__facts"><span>Imports as historical</span></div> : null}
                {!editing && value.notes.trim() ? <p className="marginalia-import-session__note">{value.notes}</p> : null}
              </div>
              {session.willImport ? <Button type="button" size="small" tone="secondary" disabled={!value.selected || applyState.pending} onClick={() => onEditingChange(key, !editing)}>{editing ? "Done" : "Edit"}</Button> : null}
            </div>
            {session.warning ? <p className="marginalia-import-warning">{session.warning}</p> : null}
            {session.willImport && editing ? <div className="marginalia-import-session__edits">
              <FormField label="Imported name" htmlFor={`marginalia-import-name-${bookIndex}-${sessionIndex}`}><input id={`marginalia-import-name-${bookIndex}-${sessionIndex}`} value={value.name} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, name: event.target.value })} /></FormField>
              <FormField label="Imported note" htmlFor={`marginalia-import-notes-${bookIndex}-${sessionIndex}`}><textarea id={`marginalia-import-notes-${bookIndex}-${sessionIndex}`} rows={2} value={value.notes} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, notes: event.target.value })} /></FormField>
            </div> : null}
          </article>;
          })}</div>
        </div>
      </section>)}
    </div>
    <ActionRowComponent state={applyState}>
      {preview.unmatchedDownloadAvailable && unmatchedSessionCount ? <Button type="button" tone="secondary" disabled>Download Unmatched Sessions ({unmatchedSessionCount})</Button> : null}
      <span className="muted">{selectedCount} {selectedCount === 1 ? "session" : "sessions"} selected</span>
      <Button type="button" disabled={!preview.canApply || selectedCount === 0 || applyState.pending} onClick={onApply}>{applyState.pending ? "Importing..." : "Import Selected Sessions"}</Button>
    </ActionRowComponent>
  </section>;
}

function BookSelectionCheckbox({ label, state, disabled, onChange }: { label: string; state: MarginaliaImportBookSelectionState; disabled: boolean; onChange: (selected: boolean) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = state === "some";
  }, [state]);
  return <input ref={inputRef} type="checkbox" checked={state === "all"} aria-checked={state === "some" ? "mixed" : state === "all"} aria-label={`Select all importable sessions from ${label}`} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />;
}

function MarginaliaImportResultRegion({ result }: { result: ReadingImportResult }) {
  return <Surface title="Import complete">
    <div className="marginalia-import-summary">
      <Badge tone="success">{result.summary.sessionsCreated} sessions created</Badge>
      <Badge>{result.summary.annotationsCreated} annotations created</Badge>
      <Badge>{result.summary.booksMatched} books matched</Badge>
      {result.summary.booksSkipped ? <Badge>{result.summary.booksSkipped} books skipped</Badge> : null}
    </div>
    {result.warnings.length ? <ul>{result.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : null}
    <div className="marginalia-import-result-actions"><Link className="button" to="/marginalia">Back to My Marginalia</Link></div>
  </Surface>;
}
