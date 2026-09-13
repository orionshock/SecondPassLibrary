import { FormField } from "../../../components/UiPrimitives";
import {
  DESCRIPTIVE_PROSE_MAX_LENGTH,
  LimitedRichTextEditor,
} from "../../../components/LimitedRichTextEditor";
import { fieldError } from "../../../shared/feedback/mutationState";
import type { BookEditDraft } from "./bookEditDraft";

export function BookEditBookPageRegion({ draft, error, disabled = false, onChange }: {
  draft: BookEditDraft;
  error?: Error;
  disabled?: boolean;
  onChange: <K extends keyof BookEditDraft>(field: K, value: BookEditDraft[K]) => void;
}) {
  return <section className="book-edit-panel">
    <FormField label="Title" htmlFor="book-edit-title" error={fieldError(error, "title")}>
      <input id="book-edit-title" maxLength={512} required value={draft.title} disabled={disabled} onChange={(event) => onChange("title", event.target.value)} />
    </FormField>
    <FormField label="Sort title" htmlFor="book-edit-sort-title" error={fieldError(error, "sortTitle")}>
      <input id="book-edit-sort-title" maxLength={512} value={draft.sortTitle} disabled={disabled} onChange={(event) => onChange("sortTitle", event.target.value)} />
    </FormField>
    <FormField label="Subtitle" htmlFor="book-edit-subtitle" error={fieldError(error, "subtitle")}>
      <input id="book-edit-subtitle" maxLength={512} value={draft.subtitle} disabled={disabled} onChange={(event) => onChange("subtitle", event.target.value)} />
    </FormField>
    <FormField label="Description" htmlFor="book-edit-description" error={fieldError(error, "description")}>
      <LimitedRichTextEditor id="book-edit-description" value={draft.description} disabled={disabled} maxLength={DESCRIPTIVE_PROSE_MAX_LENGTH} onChange={(value) => onChange("description", value)} />
    </FormField>
  </section>;
}
