import type { BookIdentifierScheme } from "@second-pass/spl-api";
import { useRef } from "react";

import { AddIconButton } from "../../../components/icons/AddIconButton";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
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
    <div className="book-edit-identifier-header" aria-hidden="true"><span>Scheme</span><span>Value</span><span>Remove</span></div>
    {draft.identifiers.map((identifier, index) => <div className="book-edit-identifier-row" key={identifier.key}>
      <div className="book-edit-identifier-field">
        <select
          id={`book-edit-identifier-scheme-${index}`}
          aria-label={`Identifier ${index + 1} scheme`}
          value={identifier.scheme}
          onChange={(event) => updateIdentifier(index, "scheme", event.target.value as BookIdentifierScheme)}
        >
          {bookIdentifierSchemeOptions.map((scheme) => <option key={scheme} value={scheme}>{bookIdentifierLabel(scheme)}</option>)}
        </select>
        {fieldError(error, `identifiers.${index}.scheme`) ? <span className="field-error">{fieldError(error, `identifiers.${index}.scheme`)}</span> : null}
      </div>
      <div className="book-edit-identifier-field">
        <input
          id={`book-edit-identifier-value-${index}`}
          aria-label={`Identifier ${index + 1} value`}
          maxLength={512}
          value={identifier.value}
          onChange={(event) => updateIdentifier(index, "value", event.target.value)}
        />
        {fieldError(error, `identifiers.${index}.value`) ? <span className="field-error">{fieldError(error, `identifiers.${index}.value`)}</span> : null}
      </div>
      <RemoveIconButton
        type="button"
        label={`Remove ${bookIdentifierLabel(identifier.scheme)} identifier`}
        onClick={() => onChange("identifiers", draft.identifiers.filter((_, currentIndex) => currentIndex !== index))}
      />
    </div>)}
    {fieldError(error, "identifiers") ? <span className="field-error">{fieldError(error, "identifiers")}</span> : null}
    <div className="book-edit-identifier-add"><AddIconButton type="button" label="Add identifier" onClick={addIdentifier} /><span>Add identifier</span></div>
  </section>;
}
