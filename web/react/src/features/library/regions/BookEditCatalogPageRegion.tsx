import { useState } from "react";

import type { CatalogTag } from "@second-pass/spl-api";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button, FormField } from "../../../components/ui";
import { fieldError } from "../../../shared/feedback/mutationState";
import type { BookEditDraft, PublicationPrecision } from "../bookEditDraft";

export function BookEditCatalogPageRegion({ draft, error, tags, tagsLoading, tagsError, onRetryTags, onChange }: {
  draft: BookEditDraft;
  error?: Error;
  tags: CatalogTag[];
  tagsLoading: boolean;
  tagsError?: Error;
  onRetryTags: () => void;
  onChange: <K extends keyof BookEditDraft>(field: K, value: BookEditDraft[K]) => void;
}) {
  const [tagName, setTagName] = useState("");
  const addTag = () => {
    const name = tagName.trim();
    if (!name || draft.catalogTagNames.some((value) => value.toLocaleLowerCase() === name.toLocaleLowerCase())) return;
    onChange("catalogTagNames", [...draft.catalogTagNames, name]);
    setTagName("");
  };
  const precision = draft.publishedDatePrecision;
  return <section className="book-edit-panel" role="tabpanel">
    <FormField label="Publisher" htmlFor="book-edit-publisher" error={fieldError(error, "publisher")}>
      <input id="book-edit-publisher" maxLength={255} value={draft.publisher} onChange={(event) => onChange("publisher", event.target.value)} />
    </FormField>
    <FormField label="Language" htmlFor="book-edit-language" error={fieldError(error, "language")}>
      <input id="book-edit-language" maxLength={64} value={draft.language} onChange={(event) => onChange("language", event.target.value)} />
    </FormField>
    <FormField label="Date precision" htmlFor="book-edit-date-precision" error={fieldError(error, "publishedDatePrecision")}>
      <select id="book-edit-date-precision" value={precision} onChange={(event) => onChange("publishedDatePrecision", event.target.value as PublicationPrecision)}>
        <option value="">No date</option><option value="year">Year</option><option value="month">Month</option><option value="day">Day</option>
      </select>
    </FormField>
    {precision ? <FormField label="Year" htmlFor="book-edit-year" error={fieldError(error, "publishedYear")}>
      <input id="book-edit-year" inputMode="numeric" value={draft.publishedYear} onChange={(event) => onChange("publishedYear", event.target.value)} />
    </FormField> : null}
    {precision === "month" || precision === "day" ? <FormField label="Month" htmlFor="book-edit-month" error={fieldError(error, "publishedMonth")}>
      <input id="book-edit-month" inputMode="numeric" value={draft.publishedMonth} onChange={(event) => onChange("publishedMonth", event.target.value)} />
    </FormField> : null}
    {precision === "day" ? <FormField label="Day" htmlFor="book-edit-day" error={fieldError(error, "publishedDay")}>
      <input id="book-edit-day" inputMode="numeric" value={draft.publishedDay} onChange={(event) => onChange("publishedDay", event.target.value)} />
    </FormField> : null}
    <div className="book-edit-tags">
      <span className="book-edit-field-label">Catalog Tags</span>
      <div className="book-edit-tag-list">{draft.catalogTagNames.map((name) => <span className="book-edit-tag" key={name}>{name}<button type="button" aria-label={`Remove ${name}`} onClick={() => onChange("catalogTagNames", draft.catalogTagNames.filter((value) => value !== name))}><MaterialIcon name="close" /></button></span>)}</div>
      <div className="book-edit-inline-control book-edit-tag-add">
        <input aria-label="Catalog Tag name" list={tagsError || tagsLoading ? undefined : "book-edit-tag-options"} value={tagName} onChange={(event) => setTagName(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter") { event.preventDefault(); addTag(); } }} />
        <Button type="button" onClick={addTag}>Add tag</Button>
      </div>
      {tagsLoading ? <span className="book-edit-picker-status">Loading tag suggestions...</span> : !tagsError ? <datalist id="book-edit-tag-options">{tags.map((tag) => <option key={tag.id} value={tag.name} />)}</datalist> : <div className="book-edit-picker-error"><span>Tag suggestions unavailable; typed names still work.</span><button type="button" onClick={onRetryTags}>Retry</button></div>}
      {fieldError(error, "catalogTagNames") ? <span className="field-error">{fieldError(error, "catalogTagNames")}</span> : null}
    </div>
  </section>;
}
