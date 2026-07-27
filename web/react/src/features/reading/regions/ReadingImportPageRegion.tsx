import type { ReadingImportPreview, ReadingImportResult } from "@second-pass/spl-api";
import { useEffect, useRef, type FormEvent, type RefObject } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, FormField, Surface } from "../../../components/ui";
import { HelpPopoverComponent } from "../../../components/HelpPopoverComponent";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import { readingImportBookSelectionState, readingImportSelectedCount, readingImportSessionKey, type ReadingImportBookSelectionState, type ReadingImportDraft, type ReadingImportSessionDraft } from "../readingImportDraft";

export function ReadingImportPageRegion({ preview, draft, result, editingSessionKeys, previewState, applyState, inputRef, onFileChange, onPreview, onDraftChange, onBookSelectionChange, onEditingChange, onApply }: {
  preview?: ReadingImportPreview;
  draft: ReadingImportDraft;
  editingSessionKeys: ReadonlySet<string>;
  result?: ReadingImportResult;
  previewState: MutationState;
  applyState: MutationState;
  inputRef: RefObject<HTMLInputElement | null>;
  onFileChange: (file?: File) => void;
  onPreview: (event: FormEvent<HTMLFormElement>) => void;
  onDraftChange: (key: string, value: ReadingImportSessionDraft) => void;
  onBookSelectionChange: (bookIndex: number, selected: boolean) => void;
  onEditingChange: (key: string, editing: boolean) => void;
  onApply: () => void;
}) {
  const selectedCount = readingImportSelectedCount(draft);
  return <div className="reading-import-page">
    <Surface title="Upload">
      <form className="reading-import-upload" encType="multipart/form-data" onSubmit={onPreview}>
        <p className="muted">Choose a native Second Pass marginalia JSON archive. Nothing changes until Apply.</p>
        <div className="reading-import-upload__file-row">
          <FormField label="Marginalia archive" htmlFor="reading-import-file" error={fieldError(previewState.error, "file")}>
            <input ref={inputRef} id="reading-import-file" name="file" type="file" accept=".json,application/json" disabled={previewState.pending || applyState.pending} onChange={(event) => onFileChange(event.target.files?.[0])} />
          </FormField>
          <ActionRowComponent state={previewState}><Button type="submit" disabled={previewState.pending || applyState.pending}>{previewState.pending ? "Previewing..." : "Preview"}</Button></ActionRowComponent>
        </div>
      </form>
    </Surface>
    {preview && !result ? <ReadingImportReview preview={preview} draft={draft} editingSessionKeys={editingSessionKeys} selectedCount={selectedCount} applyState={applyState} onDraftChange={onDraftChange} onBookSelectionChange={onBookSelectionChange} onEditingChange={onEditingChange} onApply={onApply} /> : null}
    {result ? <ReadingImportResultRegion result={result} /> : null}
  </div>;
}

function ReadingImportReview({ preview, draft, editingSessionKeys, selectedCount, applyState, onDraftChange, onBookSelectionChange, onEditingChange, onApply }: {
  preview: ReadingImportPreview;
  draft: ReadingImportDraft;
  editingSessionKeys: ReadonlySet<string>;
  selectedCount: number;
  applyState: MutationState;
  onDraftChange: (key: string, value: ReadingImportSessionDraft) => void;
  onBookSelectionChange: (bookIndex: number, selected: boolean) => void;
  onEditingChange: (key: string, editing: boolean) => void;
  onApply: () => void;
}) {
  const summaryWarnings = preview.warnings.filter((warning) => !/(?:reader-assisted import|second pass reader import)/i.test(warning));
  if (preview.unmatchedEntries) {
    summaryWarnings.unshift(`${preview.unmatchedEntries} exported Book ${preview.unmatchedEntries === 1 ? "entry did" : "entries did"} not match a visible local Book and ${preview.unmatchedEntries === 1 ? "requires" : "require"} Second Pass Reader Import.`);
  }

  return <section className="reading-import-review" aria-labelledby="reading-import-review-heading">
    <header className="reading-import-review__header">
      <h2 id="reading-import-review-heading">Review</h2>
      <div className="reading-import-summary" aria-label="Import preview summary">
        <Badge>{preview.summary.books} books</Badge><Badge>{preview.summary.sessions} sessions</Badge><Badge>{preview.summary.annotations} annotations</Badge>
      </div>
    </header>
    {summaryWarnings.length ? <div className="reading-import-summary__warnings">{summaryWarnings.map((warning, index) => <span className="reading-import-summary__warning" key={index}><span className="css-dot" aria-hidden="true" />{warning}</span>)}</div> : null}
    <div className="reading-import-books">
      {preview.books.map((book, bookIndex) => <section className="reading-import-book" key={bookIndex}>
        <div className="reading-import-book__cover">
          <BookCoverComponent coverUrl={book.coverUrl} title={book.title || "Imported Book"} />
        </div>
        <div className="reading-import-book__content">
          <header className="reading-import-book__header">
            <div className="reading-import-book__identity">
              {book.matchStatus === "matched" && book.sessions.some((session) => session.willImport) ? <BookSelectionCheckbox label={book.title || "Untitled Book"} state={readingImportBookSelectionState(preview, draft, bookIndex)} disabled={applyState.pending} onChange={(selected) => onBookSelectionChange(bookIndex, selected)} /> : null}
              <h2>{book.title || "Untitled Book"}</h2>{book.authors.length ? <><span className="css-dot" aria-hidden="true" /><span className="reading-import-book__authors">{book.authors.join(", ")}</span></> : null}
            </div>
            <span className="reading-import-book__match">
              {book.matchStatus === "matched"
                ? <Badge tone="success">Matched</Badge>
                : book.warning
                  ? <HelpPopoverComponent ariaLabel={`Why ${book.title || "this Book"} is unmatched`} icon="warning_amber" label="Unmatched" mouseoverText={book.warning} border borderColor="#d8b65a" color="#d8b65a" />
                  : <Badge>Unmatched</Badge>}
            </span>
          </header>
          {book.matchStatus === "matched" && book.warning ? <p className="reading-import-warning">{book.warning}</p> : null}
          <div className="reading-import-sessions">{book.sessions.map((session, sessionIndex) => {
          const key = readingImportSessionKey(bookIndex, sessionIndex);
          const value = draft[key] ?? { selected: false, name: session.name, notes: session.notes };
          const editing = editingSessionKeys.has(key);
          const sessionIdentity = <><span>{value.name.trim() || "Unnamed session"}</span><span className="css-dot" aria-hidden="true" /><span className="reading-import-session__annotation-count">{session.annotationCount} annotations</span></>;
          return <article className="reading-import-session" key={key}>
            <div className="reading-import-session__summary">
              <div>
                {session.willImport ? <label className="reading-import-session__select">
                  <input type="checkbox" checked={value.selected} disabled={applyState.pending} onChange={(event) => onDraftChange(key, { ...value, selected: event.target.checked })} />
                  {sessionIdentity}
                </label> : <div className="reading-import-session__select">{sessionIdentity}</div>}
                {session.activeWillImportAsHistorical ? <div className="reading-import-session__facts"><span>Imports as historical</span></div> : null}
                {!editing && value.notes.trim() ? <p className="reading-import-session__note">{value.notes}</p> : null}
              </div>
              {session.willImport ? <Button type="button" size="small" tone="secondary" disabled={!value.selected || applyState.pending} onClick={() => onEditingChange(key, !editing)}>{editing ? "Done" : "Edit"}</Button> : null}
            </div>
            {session.warning ? <p className="reading-import-warning">{session.warning}</p> : null}
            {session.willImport && editing ? <div className="reading-import-session__edits">
              <FormField label="Imported name" htmlFor={`reading-import-name-${bookIndex}-${sessionIndex}`}><input id={`reading-import-name-${bookIndex}-${sessionIndex}`} value={value.name} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, name: event.target.value })} /></FormField>
              <FormField label="Imported note" htmlFor={`reading-import-notes-${bookIndex}-${sessionIndex}`}><textarea id={`reading-import-notes-${bookIndex}-${sessionIndex}`} rows={2} value={value.notes} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, notes: event.target.value })} /></FormField>
            </div> : null}
          </article>;
          })}</div>
        </div>
      </section>)}
    </div>
    <ActionRowComponent state={applyState}>
      <span className="muted">{selectedCount} {selectedCount === 1 ? "session" : "sessions"} selected</span>
      <Button type="button" disabled={!preview.canApply || selectedCount === 0 || applyState.pending} onClick={onApply}>{applyState.pending ? "Applying..." : "Apply selected"}</Button>
    </ActionRowComponent>
  </section>;
}

function BookSelectionCheckbox({ label, state, disabled, onChange }: { label: string; state: ReadingImportBookSelectionState; disabled: boolean; onChange: (selected: boolean) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = state === "some";
  }, [state]);
  return <input ref={inputRef} type="checkbox" checked={state === "all"} aria-checked={state === "some" ? "mixed" : state === "all"} aria-label={`Select all importable sessions from ${label}`} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />;
}

function ReadingImportResultRegion({ result }: { result: ReadingImportResult }) {
  return <Surface title="Import complete">
    <div className="reading-import-summary">
      <Badge tone="success">{result.summary.sessionsCreated} sessions created</Badge>
      <Badge>{result.summary.annotationsCreated} annotations created</Badge>
      <Badge>{result.summary.booksMatched} books matched</Badge>
      {result.summary.booksSkipped ? <Badge>{result.summary.booksSkipped} books skipped</Badge> : null}
    </div>
    {result.warnings.length ? <ul>{result.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul> : null}
    <div className="reading-import-result-actions"><Link className="button" to="/reading">Back to My Marginalia</Link></div>
  </Surface>;
}
