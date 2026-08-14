import type { BookIdentifier } from "@second-pass/spl-api";

import { bookIdentifierLabel } from "../bookDetailPresentation";

export function BookIdentifierList({ identifiers }: { identifiers: readonly BookIdentifier[] }) {
  return <dl className="book-identifier-list-component">
    {identifiers.map((identifier) => <div key={identifier.id}>
      <dt>{bookIdentifierLabel(identifier.scheme)}</dt>
      <dd>{identifier.value}</dd>
    </div>)}
  </dl>;
}
