import type { BookIdentifierScheme } from "@second-pass/spl-api";
import { useRef } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button, FormField, IconButton } from "../../../components/ui";
import { fieldError } from "../../../shared/feedback/mutationState";
import { bookIdentifierLabel } from "../bookDetailPresentation";
import { bookIdentifierSchemeOptions, type BookEditDraft } from "../bookEditDraft";

export function BookEditIdentifiersPageRegion({ draft, error, onChange }: {
  draft: BookEditDraft;
  error?: Error;
  onChange: <K extends keyof BookEditDraft>(field: K, value: BookEditDraft[K]) => void;
}) {
  const nextKey = useRef(1);
  const updateIdentifier = (index: number, field: "scheme" | "value", value: string) => {
    const identifiers = draft.identifiers.map((identifier, currentIndex) => (
      currentIndex === index ? { ...identifier, [field]: value } : identifier
    ));
    onChange("identifiers", identifiers);
  };
  const addIdentifier = () => {
    onChange("identifiers", [
      ...draft.identifiers,
      { key: `new-identifier-${nextKey.current++}`, scheme: "isbn_13", value: "" },
    ]);
  };

  return <section className="book-edit-panel book-edit-identifiers" role="tabpanel">
    {draft.identifiers.map((identifier, index) => <div className="book-edit-identifier-row" key={identifier.key}>
      <FormField label="Scheme" htmlFor={`book-edit-identifier-scheme-${index}`} error={fieldError(error, `identifiers.${index}.scheme`)}>
        <select
          id={`book-edit-identifier-scheme-${index}`}
          value={identifier.scheme}
          onChange={(event) => updateIdentifier(index, "scheme", event.target.value as BookIdentifierScheme)}
        >
          {bookIdentifierSchemeOptions.map((scheme) => <option key={scheme} value={scheme}>{bookIdentifierLabel(scheme)}</option>)}
        </select>
      </FormField>
      <FormField label="Value" htmlFor={`book-edit-identifier-value-${index}`} error={fieldError(error, `identifiers.${index}.value`)}>
        <input
          id={`book-edit-identifier-value-${index}`}
          maxLength={512}
          value={identifier.value}
          onChange={(event) => updateIdentifier(index, "value", event.target.value)}
        />
      </FormField>
      <IconButton
        type="button"
        tone="danger"
        aria-label={`Remove ${bookIdentifierLabel(identifier.scheme)} identifier`}
        title="Remove identifier"
        onClick={() => onChange("identifiers", draft.identifiers.filter((_, currentIndex) => currentIndex !== index))}
      ><MaterialIcon name="remove" /></IconButton>
    </div>)}
    {fieldError(error, "identifiers") ? <span className="field-error">{fieldError(error, "identifiers")}</span> : null}
    <div><Button type="button" onClick={addIdentifier}>Add Identifier</Button></div>
  </section>;
}
