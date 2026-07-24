import { useState } from "react";

import type { LibraryAuthor, LibrarySeries } from "@second-pass/spl-api";
import { Button, FormField } from "../../../components/ui";
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
    <div>
      <h2>Authors</h2>
      {authorsLoading ? <p className="book-edit-picker-status">Loading Authors...</p> : authorsError ? <div className="book-edit-picker-error"><span>{authorsError.message}</span><button type="button" onClick={onRetryAuthors}>Retry</button></div> : <>
        <ol className="book-edit-author-list">{draft.authorIds.map((id, index) => <li key={id}>
          <span>{authorById.get(id)?.name ?? "Assigned author"}</span>
          <div><button type="button" disabled={index === 0} onClick={() => move(index, -1)}>Move up</button><button type="button" disabled={index === draft.authorIds.length - 1} onClick={() => move(index, 1)}>Move down</button><button type="button" onClick={() => onChange("authorIds", draft.authorIds.filter((value) => value !== id))}>Remove</button></div>
        </li>)}</ol>
        <div className="book-edit-inline-control">
          <select aria-label="Add existing Author" value={authorId} onChange={(event) => setAuthorId(event.target.value)}><option value="">Choose Author</option>{authors.filter(({ id }) => !draft.authorIds.includes(id)).map((author) => <option key={author.id} value={author.id}>{author.name}</option>)}</select>
          <Button type="button" disabled={!authorId} onClick={() => { if (authorId) onChange("authorIds", [...draft.authorIds, authorId]); setAuthorId(""); }}>Add</Button>
        </div>
      </>}
      {fieldError(error, "authorIds") ? <span className="field-error">{fieldError(error, "authorIds")}</span> : null}
    </div>
    <div>
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
