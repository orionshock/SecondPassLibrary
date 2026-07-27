import type { ReadingImportPreview, ReadingImportResult } from "@second-pass/spl-api";
import type { FormEvent, RefObject } from "react";
import { Link } from "react-router-dom";

import { Badge, Button, FormField, Surface } from "../../../components/ui";
import { BookCoverComponent } from "../../../shared/books/BookCoverComponent";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import { readingImportSelectedCount, readingImportSessionKey, type ReadingImportDraft, type ReadingImportSessionDraft } from "../readingImportDraft";

export function ReadingImportPageRegion({ fileName, preview, draft, result, previewState, applyState, inputRef, onFileChange, onPreview, onDraftChange, onApply }: {
  fileName?: string;
  preview?: ReadingImportPreview;
  draft: ReadingImportDraft;
  result?: ReadingImportResult;
  previewState: MutationState;
  applyState: MutationState;
  inputRef: RefObject<HTMLInputElement | null>;
  onFileChange: (file?: File) => void;
  onPreview: (event: FormEvent<HTMLFormElement>) => void;
  onDraftChange: (key: string, value: ReadingImportSessionDraft) => void;
  onApply: () => void;
}) {
  const selectedCount = readingImportSelectedCount(draft);
  return <div className="reading-import-page">
    <Surface title="Upload">
      <form className="reading-import-upload" encType="multipart/form-data" onSubmit={onPreview}>
        <p className="muted">Choose a native Second Pass marginalia JSON archive. Nothing changes until you review the preview and apply it.</p>
        <FormField label="Marginalia archive" htmlFor="reading-import-file" error={fieldError(previewState.error, "file")}>
          <input ref={inputRef} id="reading-import-file" name="file" type="file" accept=".json,application/json" disabled={previewState.pending || applyState.pending} onChange={(event) => onFileChange(event.target.files?.[0])} />
        </FormField>
        {fileName ? <p className="muted">Selected: {fileName}</p> : null}
        <ActionRowComponent state={previewState}><Button type="submit" disabled={previewState.pending || applyState.pending}>{previewState.pending ? "Previewing..." : "Preview"}</Button></ActionRowComponent>
      </form>
    </Surface>
    {preview && !result ? <ReadingImportReview preview={preview} draft={draft} selectedCount={selectedCount} applyState={applyState} onDraftChange={onDraftChange} onApply={onApply} /> : null}
    {result ? <ReadingImportResultRegion result={result} /> : null}
  </div>;
}

function ReadingImportReview({ preview, draft, selectedCount, applyState, onDraftChange, onApply }: {
  preview: ReadingImportPreview;
  draft: ReadingImportDraft;
  selectedCount: number;
  applyState: MutationState;
  onDraftChange: (key: string, value: ReadingImportSessionDraft) => void;
  onApply: () => void;
}) {
  return <Surface title="Review">
    <div className="reading-import-summary" aria-label="Import preview summary">
      <Badge>{preview.summary.books} books</Badge><Badge>{preview.summary.sessions} sessions</Badge><Badge>{preview.summary.annotations} annotations</Badge>
    </div>
    {preview.warnings.length ? <div className="reading-import-warnings"><strong>Warnings</strong><ul>{preview.warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></div> : null}
    {preview.unmatchedEntries ? <p className="muted">{preview.unmatchedEntries} {preview.unmatchedEntries === 1 ? "entry requires" : "entries require"} Reader-assisted import.</p> : null}
    <div className="reading-import-books">
      {preview.books.map((book, bookIndex) => <section className="reading-import-book" key={bookIndex}>
        <header className="reading-import-book__header">
          <BookCoverComponent coverUrl={book.coverUrl} title={book.title || "Imported Book"} />
          <div><h2>{book.title || "Untitled Book"}</h2>{book.authors.length ? <p>{book.authors.join(", ")}</p> : null}</div>
          <Badge tone={book.matchStatus === "matched" ? "success" : "default"}>{book.matchStatus === "matched" ? "Matched" : "Unmatched"}</Badge>
        </header>
        {book.warning ? <p className="reading-import-warning">{book.warning}</p> : null}
        <div className="reading-import-sessions">{book.sessions.map((session, sessionIndex) => {
          const key = readingImportSessionKey(bookIndex, sessionIndex);
          const value = draft[key] ?? { selected: false, name: session.name, notes: session.notes };
          return <article className="reading-import-session" key={key}>
            <label className="reading-import-session__select">
              <input type="checkbox" checked={value.selected} disabled={!session.willImport || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, selected: event.target.checked })} />
              <span>{session.name.trim() || "Unnamed session"}</span>
            </label>
            <div className="reading-import-session__facts"><span>{session.annotationCount} annotations</span>{session.activeWillImportAsHistorical ? <><span className="css-dot" aria-hidden="true" /><span>Imports as historical</span></> : null}</div>
            {session.warning ? <p className="reading-import-warning">{session.warning}</p> : null}
            {session.willImport ? <div className="reading-import-session__edits">
              <FormField label="Imported name" htmlFor={`reading-import-name-${bookIndex}-${sessionIndex}`}><input id={`reading-import-name-${bookIndex}-${sessionIndex}`} value={value.name} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, name: event.target.value })} /></FormField>
              <FormField label="Imported notes" htmlFor={`reading-import-notes-${bookIndex}-${sessionIndex}`}><textarea id={`reading-import-notes-${bookIndex}-${sessionIndex}`} rows={2} value={value.notes} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, notes: event.target.value })} /></FormField>
            </div> : null}
          </article>;
        })}</div>
      </section>)}
    </div>
    <ActionRowComponent state={applyState}>
      <span className="muted">{selectedCount} {selectedCount === 1 ? "session" : "sessions"} selected</span>
      <Button type="button" disabled={!preview.canApply || selectedCount === 0 || applyState.pending} onClick={onApply}>{applyState.pending ? "Applying..." : "Apply selected"}</Button>
    </ActionRowComponent>
  </Surface>;
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
