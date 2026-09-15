import { useState } from "react";
import { Link } from "react-router";

import { AddIconButton } from "../../../components/icons/AddIconButton";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, FormField, IconButton } from "../../../components/UiPrimitives";
import type { BreadcrumbItem } from "../../../app/navigation/breadcrumbs";
import { fieldError } from "../../../shared/feedback/mutationState";
import type { BookEditDraft } from "./bookEditDraft";
import type { BookEditAuthorChoice, BookEditSeriesChoice } from "./useBookEditChoices";
import { libraryEntityContextBreadcrumbs, libraryEntityEditPath, libraryEntityNavigationState, libraryEntityNewPath } from "../authorSeriesLifecycle";

export function BookEditAuthorsSeriesPageRegion({ draft, error, authors, series, authorQuery, seriesQuery, authorsLoading, seriesLoading, authorsError, seriesError, breadcrumbTrail, returnTo, disabled = false, onAuthorQueryChange, onSeriesQueryChange, onRetryAuthors, onRetrySeries, onChange }: {
  draft: BookEditDraft;
  error?: Error;
  authors: BookEditAuthorChoice[];
  series: BookEditSeriesChoice[];
  authorQuery: string;
  seriesQuery: string;
  authorsLoading: boolean;
  seriesLoading: boolean;
  authorsError?: Error;
  seriesError?: Error;
  breadcrumbTrail: readonly BreadcrumbItem[];
  returnTo: string;
  disabled?: boolean;
  onAuthorQueryChange: (query: string) => void;
  onSeriesQueryChange: (query: string) => void;
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
  return <section className="book-edit-panel book-edit-relationships">
    <div className="book-edit-relationship-group">
      <div className="book-edit-relationship-heading book-edit-relationship-heading--actions-only"><Link
        className="button button--small button--secondary"
        to={libraryEntityNewPath("author")}
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : undefined}
        onClick={(event) => { if (disabled) event.preventDefault(); }}
        state={libraryEntityNavigationState({ breadcrumbs: libraryEntityContextBreadcrumbs(breadcrumbTrail, "author", "new", returnTo), returnTo })}
      >New Author</Link></div>
      <div className="book-edit-author-grid">
        <h2>Authors</h2>
        <ol className="book-edit-author-list">{draft.authorIds.map((id, index) => {
          const author = authorById.get(id);
          const label = author ? distinctChoiceLabel(author, authors) : "Assigned author";
          return <li key={id}>
            <span>{label}</span>
            <div className="book-edit-author-actions">
              <IconButton type="button" aria-label={`Move ${label} up`} title="Move up" disabled={disabled || index === 0} onClick={() => move(index, -1)}><MaterialIcon name="arrow_upward" /></IconButton>
              <IconButton type="button" aria-label={`Move ${label} down`} title="Move down" disabled={disabled || index === draft.authorIds.length - 1} onClick={() => move(index, 1)}><MaterialIcon name="arrow_downward" /></IconButton>
              <RemoveIconButton type="button" label={`Remove ${label}`} disabled={disabled} onClick={() => onChange("authorIds", draft.authorIds.filter((value) => value !== id))} />
            </div>
          </li>;
        })}</ol>
        <label htmlFor="book-edit-author-search">Find Author</label>
        <input id="book-edit-author-search" type="search" value={authorQuery} disabled={disabled} onChange={(event) => onAuthorQueryChange(event.target.value)} />
        {authorsLoading ? <p className="book-edit-picker-status" aria-live="polite">Loading Authors...</p> : null}
        {authorsError ? <div className="book-edit-picker-error" role="alert"><span>{authorsError.message}</span><Button type="button" size="small" tone="secondary" onClick={onRetryAuthors}>Retry</Button></div> : null}
        <label htmlFor="book-edit-add-author">Add existing Author</label>
        <div className="book-edit-inline-control">
          <select id="book-edit-add-author" value={authorId} disabled={disabled || authorsLoading || Boolean(authorsError)} onChange={(event) => setAuthorId(event.target.value)}><option value="">Choose Author</option>{authors.filter(({ id }) => !draft.authorIds.includes(id)).map((author) => <option key={author.id} value={author.id}>{distinctChoiceLabel(author, authors)}</option>)}</select>
          <AddIconButton type="button" label="Add author" disabled={disabled || authorsLoading || Boolean(authorsError) || !authorId} onClick={() => { if (authorId) onChange("authorIds", [...draft.authorIds, authorId]); setAuthorId(""); }} />
        </div>
      </div>
      {fieldError(error, "authorIds") ? <span className="field-error">{fieldError(error, "authorIds")}</span> : null}
    </div>
    <div className="book-edit-relationship-group book-edit-series-fields">
      <div className="book-edit-relationship-heading"><h2>Series</h2><Link
        className="button button--small button--secondary"
        to={libraryEntityNewPath("series")}
        aria-disabled={disabled}
        tabIndex={disabled ? -1 : undefined}
        onClick={(event) => { if (disabled) event.preventDefault(); }}
        state={libraryEntityNavigationState({ breadcrumbs: libraryEntityContextBreadcrumbs(breadcrumbTrail, "series", "new", returnTo), returnTo })}
      >New Series</Link></div>
      <FormField label="Find Series" htmlFor="book-edit-series-search">
        <input id="book-edit-series-search" type="search" value={seriesQuery} disabled={disabled} onChange={(event) => onSeriesQueryChange(event.target.value)} />
      </FormField>
      {seriesLoading ? <p className="book-edit-picker-status" aria-live="polite">Loading Series...</p> : null}
      {seriesError ? <div className="book-edit-picker-error" role="alert"><span>{seriesError.message}</span><Button type="button" size="small" tone="secondary" onClick={onRetrySeries}>Retry</Button></div> : null}
      <FormField label="Assigned Series" htmlFor="book-edit-series" error={fieldError(error, "seriesId")}>
        <select id="book-edit-series" value={draft.seriesId ?? ""} disabled={disabled} onChange={(event) => { const id = event.target.value || null; onChange("seriesId", id); if (!id) onChange("seriesIndex", ""); }}><option value="">No Series</option>{series.map((item) => <option key={item.id} value={item.id}>{distinctChoiceLabel(item, series)}</option>)}</select>
      </FormField>
      <FormField label="Series index" htmlFor="book-edit-series-index" error={fieldError(error, "seriesIndex")}>
        <input id="book-edit-series-index" type="number" min="0.01" step="0.01" disabled={disabled || !draft.seriesId} inputMode="decimal" value={draft.seriesIndex} onChange={(event) => onChange("seriesIndex", event.target.value)} />
      </FormField>
      {draft.seriesId && series.find(({ id }) => id === draft.seriesId) ? <Link
          className="book-edit-assigned-series-link"
          to={libraryEntityEditPath("series", draft.seriesId)}
          aria-disabled={disabled}
          tabIndex={disabled ? -1 : undefined}
          onClick={(event) => { if (disabled) event.preventDefault(); }}
          state={libraryEntityNavigationState({ breadcrumbs: libraryEntityContextBreadcrumbs(breadcrumbTrail, "series", "edit", returnTo, series.find(({ id }) => id === draft.seriesId)?.name, draft.seriesId), returnTo })}
      >Edit assigned Series</Link> : null}
    </div>
  </section>;
}

function distinctChoiceLabel(
  choice: { id: string; name: string; sortName?: string },
  choices: readonly { id: string; name: string }[],
): string {
  const duplicateName = choices.some((other) => (
    other.id !== choice.id && other.name === choice.name
  ));
  if (!duplicateName) return choice.name;
  return `${choice.name} — ${choice.sortName || "entity"} · ${choice.id}`;
}
