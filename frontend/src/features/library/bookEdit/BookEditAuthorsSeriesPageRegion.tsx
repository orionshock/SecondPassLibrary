import { useState } from "react";
import { Link } from "react-router";

import type { LibraryAuthor, LibrarySeries } from "@second-pass/spl-api";
import { AddIconButton } from "../../../components/icons/AddIconButton";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, FormField, IconButton } from "../../../components/UiPrimitives";
import type { BreadcrumbItem } from "../../../app/navigation/breadcrumbs";
import { fieldError } from "../../../shared/feedback/mutationState";
import type { BookEditDraft } from "./bookEditDraft";
import { libraryEntityContextBreadcrumbs, libraryEntityEditPath, libraryEntityNavigationState, libraryEntityNewPath } from "../authorSeriesLifecycle";

export function BookEditAuthorsSeriesPageRegion({ draft, error, authors, series, authorsLoading, seriesLoading, authorsError, seriesError, breadcrumbTrail, returnTo, onRetryAuthors, onRetrySeries, onChange }: {
  draft: BookEditDraft;
  error?: Error;
  authors: LibraryAuthor[];
  series: LibrarySeries[];
  authorsLoading: boolean;
  seriesLoading: boolean;
  authorsError?: Error;
  seriesError?: Error;
  breadcrumbTrail: readonly BreadcrumbItem[];
  returnTo: string;
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
      <div className="book-edit-relationship-heading book-edit-relationship-heading--actions-only"><Link
        className="button button--small button--secondary"
        to={libraryEntityNewPath("author")}
        state={libraryEntityNavigationState({ breadcrumbs: libraryEntityContextBreadcrumbs(breadcrumbTrail, "author", "new", returnTo), returnTo })}
      >New Author</Link></div>
      {authorsLoading ? <p className="book-edit-picker-status">Loading Authors...</p> : authorsError ? <div className="book-edit-picker-error"><span>{authorsError.message}</span><Button type="button" size="small" tone="secondary" onClick={onRetryAuthors}>Retry</Button></div> : <>
        <div className="book-edit-author-grid">
          <h2>Authors</h2>
          <ol className="book-edit-author-list">{draft.authorIds.map((id, index) => <li key={id}>
            <span>{authorById.get(id)?.name ?? "Assigned author"}</span>
            <div className="book-edit-author-actions">
              <IconButton type="button" aria-label={`Move ${authorById.get(id)?.name ?? "Author"} up`} title="Move up" disabled={index === 0} onClick={() => move(index, -1)}><MaterialIcon name="arrow_upward" /></IconButton>
              <IconButton type="button" aria-label={`Move ${authorById.get(id)?.name ?? "Author"} down`} title="Move down" disabled={index === draft.authorIds.length - 1} onClick={() => move(index, 1)}><MaterialIcon name="arrow_downward" /></IconButton>
              <RemoveIconButton type="button" label={`Remove ${authorById.get(id)?.name ?? "Author"}`} onClick={() => onChange("authorIds", draft.authorIds.filter((value) => value !== id))} />
            </div>
          </li>)}</ol>
          <label htmlFor="book-edit-add-author">Add existing Author</label>
          <div className="book-edit-inline-control">
            <select id="book-edit-add-author" value={authorId} onChange={(event) => setAuthorId(event.target.value)}><option value="">Choose Author</option>{authors.filter(({ id }) => !draft.authorIds.includes(id)).map((author) => <option key={author.id} value={author.id}>{author.name}</option>)}</select>
            <AddIconButton type="button" label="Add author" disabled={!authorId} onClick={() => { if (authorId) onChange("authorIds", [...draft.authorIds, authorId]); setAuthorId(""); }} />
          </div>
        </div>
      </>}
      {fieldError(error, "authorIds") ? <span className="field-error">{fieldError(error, "authorIds")}</span> : null}
    </div>
    <div className="book-edit-relationship-group book-edit-series-fields">
      <div className="book-edit-relationship-heading"><h2>Series</h2><Link
        className="button button--small button--secondary"
        to={libraryEntityNewPath("series")}
        state={libraryEntityNavigationState({ breadcrumbs: libraryEntityContextBreadcrumbs(breadcrumbTrail, "series", "new", returnTo), returnTo })}
      >New Series</Link></div>
      {seriesLoading ? <p className="book-edit-picker-status">Loading Series...</p> : seriesError ? <div className="book-edit-picker-error"><span>{seriesError.message}</span><Button type="button" size="small" tone="secondary" onClick={onRetrySeries}>Retry</Button></div> : <>
        <FormField label="Assigned Series" htmlFor="book-edit-series" error={fieldError(error, "seriesId")}>
          <select id="book-edit-series" value={draft.seriesId ?? ""} onChange={(event) => { const id = event.target.value || null; onChange("seriesId", id); if (!id) onChange("seriesIndex", ""); }}><option value="">No Series</option>{series.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select>
        </FormField>
        <FormField label="Series index" htmlFor="book-edit-series-index" error={fieldError(error, "seriesIndex")}>
          <input id="book-edit-series-index" type="number" min="0.01" step="0.01" disabled={!draft.seriesId} inputMode="decimal" value={draft.seriesIndex} onChange={(event) => onChange("seriesIndex", event.target.value)} />
        </FormField>
        {draft.seriesId && series.find(({ id }) => id === draft.seriesId) ? <Link
          className="book-edit-assigned-series-link"
          to={libraryEntityEditPath("series", draft.seriesId)}
          state={libraryEntityNavigationState({ breadcrumbs: libraryEntityContextBreadcrumbs(breadcrumbTrail, "series", "edit", returnTo, series.find(({ id }) => id === draft.seriesId)?.name, draft.seriesId), returnTo })}
        >Edit assigned Series</Link> : null}
      </>}
    </div>
  </section>;
}
