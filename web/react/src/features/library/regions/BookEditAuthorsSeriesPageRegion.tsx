import { useState } from "react";

import type { LibraryAuthor, LibrarySeries } from "@second-pass/spl-api";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button, FormField, IconButton } from "../../../components/ui";
import { fieldError } from "../../../shared/feedback/mutationState";
import type { BookEditDraft } from "../bookEditDraft";

export function BookEditAuthorsSeriesPageRegion({ draft, error, authors, series, authorsLoading, seriesLoading, authorsError, seriesError, onRetryAuthors, onRetrySeries, onChange }: {
  draft: BookEditDraft;
  error?: Error;
  authors: LibraryAuthor[];
  series: LibrarySeries[];
  authorsLoading: boolean;
  seriesLoading: boolean;
  authorsError?: Error;
  seriesError?: Error;
  onRetryAuthors: () => void;
  onRetrySeries: () => void;
  onChange: <K extends keyof BookEditDraft>(field: K, value: BookEditDraft[K]) => void;
}) {
  const [authorId, setAuthorId] = useState("");
  const authorById = new Map(authors.map((author) => [author.id, author]));
  const move = (index: number, delta: number) => {
    const next = [...draft.authorIds];
    [next[index], next[index + delta]] = [next[index + delta], next[index]];
    onChange("authorIds", next);
  };
  return <section className="book-edit-panel book-edit-relationships" role="tabpanel">
    <div className="book-edit-relationship-group">
      <h2>Authors</h2>
      {authorsLoading ? <p className="book-edit-picker-status">Loading Authors...</p> : authorsError ? <div className="book-edit-picker-error"><span>{authorsError.message}</span><button type="button" onClick={onRetryAuthors}>Retry</button></div> : <>
        <ol className="book-edit-author-list">{draft.authorIds.map((id, index) => <li key={id}>
          <span>{authorById.get(id)?.name ?? "Assigned author"}</span>
          <div className="book-edit-author-actions">
            <IconButton type="button" aria-label={`Move ${authorById.get(id)?.name ?? "Author"} up`} title="Move up" disabled={index === 0} onClick={() => move(index, -1)}><MaterialIcon name="arrow_upward" /></IconButton>
            <IconButton type="button" aria-label={`Move ${authorById.get(id)?.name ?? "Author"} down`} title="Move down" disabled={index === draft.authorIds.length - 1} onClick={() => move(index, 1)}><MaterialIcon name="arrow_downward" /></IconButton>
            <IconButton type="button" tone="danger" aria-label={`Remove ${authorById.get(id)?.name ?? "Author"}`} title="Remove" onClick={() => onChange("authorIds", draft.authorIds.filter((value) => value !== id))}><MaterialIcon name="remove" /></IconButton>
          </div>
        </li>)}</ol>
        <div className="book-edit-inline-control book-edit-author-add">
          <select aria-label="Add existing Author" value={authorId} onChange={(event) => setAuthorId(event.target.value)}><option value="">Choose Author</option>{authors.filter(({ id }) => !draft.authorIds.includes(id)).map((author) => <option key={author.id} value={author.id}>{author.name}</option>)}</select>
          <Button type="button" disabled={!authorId} onClick={() => { if (authorId) onChange("authorIds", [...draft.authorIds, authorId]); setAuthorId(""); }}>Add</Button>
        </div>
      </>}
      {fieldError(error, "authorIds") ? <span className="field-error">{fieldError(error, "authorIds")}</span> : null}
    </div>
    <div className="book-edit-relationship-group book-edit-series-fields">
      <h2>Series</h2>
      {seriesLoading ? <p className="book-edit-picker-status">Loading Series...</p> : seriesError ? <div className="book-edit-picker-error"><span>{seriesError.message}</span><button type="button" onClick={onRetrySeries}>Retry</button></div> : <>
        <FormField label="Assigned Series" htmlFor="book-edit-series" error={fieldError(error, "seriesId")}>
          <select id="book-edit-series" value={draft.seriesId ?? ""} onChange={(event) => { const id = event.target.value || null; onChange("seriesId", id); if (!id) onChange("seriesIndex", ""); }}><option value="">No Series</option>{series.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        </FormField>
        <FormField label="Series index" htmlFor="book-edit-series-index" error={fieldError(error, "seriesIndex")}>
          <input id="book-edit-series-index" disabled={!draft.seriesId} inputMode="decimal" value={draft.seriesIndex} onChange={(event) => onChange("seriesIndex", event.target.value)} />
        </FormField>
      </>}
    </div>
  </section>;
}
