import type { MarginaliaImportApplyResult, MarginaliaImportPreview } from "@second-pass/spl-api";
import { useEffect, useRef, type FormEvent, type RefObject } from "react";
import { Link } from "react-router";

import { Badge, Button, FormField, Surface } from "../../../components/UiPrimitives";
import { HelpPopover } from "../../../components/HelpPopover";
import { BookCover } from "../../../shared/books/BookCover";
import { marginaliaSessionDisplayName } from "../../../shared/marginaliaSessionDisplayName";
import { ActionFeedback } from "../../../shared/feedback/ActionFeedback";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRow } from "../../../shared/forms/ActionRow";
import { marginaliaImportBookSelectionState, marginaliaImportSelectedCount, type MarginaliaImportBookSelectionState, type MarginaliaImportDraft, type MarginaliaImportSessionDraft } from "./marginaliaImportDraft";

export function MarginaliaImportPageRegion({ preview, draft, result, editingSessionKeys, previewState, applyState, downloadState, inputRef, includeEmptySessions, onIncludeEmptySessionsChange, onFileChange, onPreview, onDraftChange, onBookSelectionChange, onEditingChange, onDownloadUnmatched, onApply }: {
  preview?: MarginaliaImportPreview;
  draft: MarginaliaImportDraft;
  editingSessionKeys: ReadonlySet<string>;
  result?: MarginaliaImportApplyResult;
  previewState: MutationState;
  applyState: MutationState;
  downloadState: MutationState;
  inputRef: RefObject<HTMLInputElement | null>;
  includeEmptySessions: boolean;
  onIncludeEmptySessionsChange: (include: boolean) => void;
  onFileChange: (file?: File) => void;
  onPreview: (event: FormEvent<HTMLFormElement>) => void;
  onDraftChange: (key: string, value: MarginaliaImportSessionDraft) => void;
  onBookSelectionChange: (bookCandidateId: string, selected: boolean) => void;
  onEditingChange: (key: string, editing: boolean) => void;
  onDownloadUnmatched: () => void;
  onApply: () => void;
}) {
  const selectedCount = marginaliaImportSelectedCount(draft);
  return <div className="marginalia-import-page">
    <Surface title="Upload">
      <form className="marginalia-import-upload" encType="multipart/form-data" onSubmit={onPreview}>
        <p className="muted">Choose a Marginalia archive exported from Second Pass Library. Nothing is imported until you confirm the preview.</p>
        <div className="marginalia-import-upload__file-row">
          <FormField label="Marginalia archive" htmlFor="marginalia-import-file" error={fieldError(previewState.error, "file")}>
            <input ref={inputRef} id="marginalia-import-file" name="file" type="file" accept=".json,application/json" disabled={previewState.pending || applyState.pending} onChange={(event) => onFileChange(event.target.files?.[0])} />
          </FormField>
          <label className="marginalia-empty-sessions-toggle"><input type="checkbox" checked={includeEmptySessions} disabled={previewState.pending || applyState.pending} onChange={(event) => onIncludeEmptySessionsChange(event.target.checked)} />Include empty Reading Sessions</label>
          <ActionRow state={previewState}><Button type="submit" disabled={previewState.pending || applyState.pending}>{previewState.pending ? "Previewing..." : "Preview"}</Button></ActionRow>
        </div>
      </form>
    </Surface>
    {preview && !result ? <MarginaliaImportReview preview={preview} draft={draft} editingSessionKeys={editingSessionKeys} selectedCount={selectedCount} applyState={applyState} downloadState={downloadState} onDraftChange={onDraftChange} onBookSelectionChange={onBookSelectionChange} onEditingChange={onEditingChange} onDownloadUnmatched={onDownloadUnmatched} onApply={onApply} /> : null}
    {result ? <MarginaliaImportResultRegion result={result} downloadState={downloadState} onDownloadUnmatched={onDownloadUnmatched} /> : null}
  </div>;
}

function MarginaliaImportReview({ preview, draft, editingSessionKeys, selectedCount, applyState, downloadState, onDraftChange, onBookSelectionChange, onEditingChange, onDownloadUnmatched, onApply }: {
  preview: MarginaliaImportPreview;
  draft: MarginaliaImportDraft;
  editingSessionKeys: ReadonlySet<string>;
  selectedCount: number;
  applyState: MutationState;
  downloadState: MutationState;
  onDraftChange: (key: string, value: MarginaliaImportSessionDraft) => void;
  onBookSelectionChange: (bookCandidateId: string, selected: boolean) => void;
  onEditingChange: (key: string, editing: boolean) => void;
  onDownloadUnmatched: () => void;
  onApply: () => void;
}) {
  const summaryWarnings = preview.warnings.filter((warning) => warning.candidateId === undefined);
  return <section className="marginalia-import-review" aria-labelledby="marginalia-import-review-heading">
    <header className="marginalia-import-review__header">
      <h2 id="marginalia-import-review-heading">Review</h2>
      <div className="marginalia-import-summary" aria-label="Import preview summary">
        <Badge>{preview.summary.bookCount} Books</Badge><Badge>{preview.summary.readingSessionCount} Reading Sessions</Badge><Badge>{preview.summary.annotationCount} annotations</Badge>
      </div>
    </header>
    {preview.unmatchedBookCount ? <p className="marginalia-import-warning">{preview.unmatchedBookCount} {preview.unmatchedBookCount === 1 ? "Book has" : "Books have"} no exact EPUB checksum match. Download the unmatched Reading Sessions or import the matching EPUB and preview again.</p> : null}
    {summaryWarnings.length ? <div className="marginalia-import-summary__warnings">{summaryWarnings.map((warning) => <span className="marginalia-import-summary__warning" key={warning.code}><span className="css-dot" aria-hidden="true" />{warning.message}</span>)}</div> : null}
    <div className="marginalia-import-books">
      {preview.books.map((book, bookIndex) => <section className="marginalia-import-book" key={book.candidateId}>
        <div className="marginalia-import-book__cover">
          <BookCover coverUrl={null} title={book.title || "Imported Book"} />
        </div>
        <div className="marginalia-import-book__content">
          <header className="marginalia-import-book__header">
            <div className="marginalia-import-book__identity">
              {book.match.status === "matched" && book.readingSessions.some((session) => session.willImport) ? <BookSelectionCheckbox label={book.title || "Untitled Book"} state={marginaliaImportBookSelectionState(preview, draft, book.candidateId)} disabled={applyState.pending} onChange={(selected) => onBookSelectionChange(book.candidateId, selected)} /> : null}
              <h2>{book.title || "Untitled Book"}</h2>{book.authors.length ? <><span className="css-dot" aria-hidden="true" /><span className="marginalia-import-book__authors">{book.authors.join(", ")}</span></> : null}
            </div>
            <span className="marginalia-import-book__match">
              {book.match.status === "matched"
                ? <Badge tone="success">Matched Book</Badge>
                : <Badge>{book.match.reason === "book_inaccessible" ? "Unavailable Book" : "Unmatched Book"}</Badge>}
            </span>
          </header>
          {book.match.status === "unmatched" ? <p className="marginalia-import-warning">{unmatchedBookGuidance(book.match.reason)}</p> : null}
          <div className="marginalia-import-sessions">{book.readingSessions.map((session, sessionIndex) => {
          const key = session.candidateId;
          const value = draft[key] ?? { selected: false, name: session.name, notes: session.notes };
          const editing = editingSessionKeys.has(key);
          const sessionName = marginaliaSessionDisplayName({ id: session.candidateId, name: value.name });
          const sessionFacts = <><span className="css-dot" aria-hidden="true" /><span className="marginalia-import-session__annotation-count">{session.annotationCount} annotations</span></>;
          const duplicateWarning = session.warnings.find((warning) => warning.code === "POSSIBLE_DUPLICATE_SESSION");
          return <article className="marginalia-import-session" key={key}>
            <div className="marginalia-import-session__summary">
              <div>
                {session.willImport ? <div className="marginalia-import-session__select">
                  <label><input type="checkbox" checked={value.selected} disabled={applyState.pending} onChange={(event) => onDraftChange(key, { ...value, selected: event.target.checked })} /><span>{sessionName}</span></label>
                  {session.possibleDuplicate && duplicateWarning ? <HelpPopover ariaLabel={`Why ${sessionName} may be a duplicate Reading Session`} label="Possible duplicate" mouseoverText={duplicateWarning.message} border borderColor="#8f783f" color="#c2a85f" /> : null}
                  {sessionFacts}
                </div> : <div className="marginalia-import-session__select"><span>{sessionName}</span>{sessionFacts}</div>}
                {session.sourceStatus === "active" ? <div className="marginalia-import-session__facts"><span>Active source Reading Session imports as closed</span></div> : null}
                {!editing && value.notes.trim() ? <p className="marginalia-import-session__note">{value.notes}</p> : null}
              </div>
              {session.willImport ? <Button type="button" size="small" tone="secondary" aria-label={`${editing ? "Finish editing" : "Edit"} ${sessionName}`} disabled={!value.selected || applyState.pending} onClick={() => onEditingChange(key, !editing)}>{editing ? "Done" : "Edit"}</Button> : null}
            </div>
            {session.warnings.filter((warning) => warning.code !== "POSSIBLE_DUPLICATE_SESSION").map((warning) => <p className="marginalia-import-warning" key={warning.code}>{warning.message}</p>)}
            {session.willImport && editing ? <div className="marginalia-import-session__edits">
              <FormField label="Imported name" htmlFor={`marginalia-import-name-${bookIndex}-${sessionIndex}`}><input id={`marginalia-import-name-${bookIndex}-${sessionIndex}`} value={value.name} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, name: event.target.value })} /></FormField>
              <FormField label="Imported note" htmlFor={`marginalia-import-notes-${bookIndex}-${sessionIndex}`}><textarea id={`marginalia-import-notes-${bookIndex}-${sessionIndex}`} rows={2} value={value.notes} disabled={!value.selected || applyState.pending} onChange={(event) => onDraftChange(key, { ...value, notes: event.target.value })} /></FormField>
            </div> : null}
          </article>;
          })}</div>
        </div>
      </section>)}
    </div>
    <ActionRow state={applyState}>
      {preview.unmatchedDownloadableReadingSessionCount > 0 ? <span className="marginalia-import-download-action"><ActionFeedback state={downloadState} /><Button type="button" tone="secondary" disabled={downloadState.pending || applyState.pending} onClick={onDownloadUnmatched}>{downloadState.pending ? "Downloading…" : `Download unmatched (${preview.unmatchedDownloadableReadingSessionCount})`}</Button></span> : null}
      <span className="muted">{selectedCount} {selectedCount === 1 ? "Reading Session" : "Reading Sessions"} selected</span>
      <Button type="button" disabled={!preview.canApply || selectedCount === 0 || applyState.pending || downloadState.pending} onClick={onApply}>{applyState.pending ? "Importing…" : "Import selected"}</Button>
    </ActionRow>
  </section>;
}

function unmatchedBookGuidance(reason: "not_found" | "ambiguous_match" | "book_inaccessible") {
  if (reason === "book_inaccessible") {
    return "The matching Book exists, but you cannot currently access it. Download this Reading Session or restore access and preview again.";
  }
  if (reason === "ambiguous_match") {
    return "More than one visible Book has this EPUB checksum. Fix the duplicate Book files, then preview again.";
  }
  return "No visible Book has this exact EPUB checksum. Import the matching EPUB, then preview again.";
}

function BookSelectionCheckbox({ label, state, disabled, onChange }: { label: string; state: MarginaliaImportBookSelectionState; disabled: boolean; onChange: (selected: boolean) => void }) {
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (inputRef.current) inputRef.current.indeterminate = state === "some";
  }, [state]);
  return <input ref={inputRef} type="checkbox" checked={state === "all"} aria-checked={state === "some" ? "mixed" : state === "all"} aria-label={`Select all importable Reading Sessions from ${label}`} disabled={disabled} onChange={(event) => onChange(event.target.checked)} />;
}

function MarginaliaImportResultRegion({ result, downloadState, onDownloadUnmatched }: { result: MarginaliaImportApplyResult; downloadState: MutationState; onDownloadUnmatched: () => void }) {
  return <Surface title="Import complete">
    <div className="marginalia-import-summary">
      <Badge tone="success">{result.importedReadingSessionCount} {result.importedReadingSessionCount === 1 ? "Reading Session" : "Reading Sessions"} created</Badge>
      <Badge>{result.importedAnnotationCount} annotations created</Badge>
    </div>
    {result.unmatchedReadingSessionCount > 0 ? <div className="marginalia-import-warning">
      <p>{result.unmatchedReadingSessionCount} unmatched {result.unmatchedReadingSessionCount === 1 ? "Reading Session remains" : "Reading Sessions remain"}. Download them, then retry after restoring Book access.</p>
      {result.unmatchedBooks.length ? <ul>{result.unmatchedBooks.map((book) => <li key={book.candidateId}>{book.title}</li>)}</ul> : null}
    </div> : null}
    {result.readingSessions.length ? <ul>{result.readingSessions.map((session) => <li key={session.candidateId}><Link to={`/marginalia/sessions/${encodeURIComponent(session.readingSessionId)}`}>{marginaliaSessionDisplayName({ id: session.readingSessionId, name: session.name })}</Link> · {session.annotationCount} annotations · Closed</li>)}</ul> : null}
    {result.warnings.length ? <ul>{result.warnings.map((warning) => <li key={`${warning.code}:${warning.candidateId ?? "general"}`}>{warning.message}</li>)}</ul> : null}
    <div className="marginalia-import-result-actions">
      {result.unmatchedDownloadAvailable ? <><ActionFeedback state={downloadState} /><Button type="button" tone="secondary" disabled={downloadState.pending} onClick={onDownloadUnmatched}>{downloadState.pending ? "Downloading…" : `Download unmatched (${result.unmatchedDownloadableReadingSessionCount})`}</Button></> : null}
      <Link className="button" to="/marginalia">Back to My Marginalia</Link>
    </div>
  </Surface>;
}
