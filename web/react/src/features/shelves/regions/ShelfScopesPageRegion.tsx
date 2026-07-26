import type { ShelfScope } from "@second-pass/spl-api";

import { Button } from "../../../components/ui";

const scopes: Array<{ id: ShelfScope; label: string }> = [
  { id: "personal", label: "Personal" },
  { id: "shared", label: "Shared by Others" },
  { id: "group", label: "Group Shelves" },
];

export function ShelfScopesPageRegion({ activeScope, onScopeChange }: {
  activeScope: ShelfScope;
  onScopeChange: (scope: ShelfScope) => void;
}) {
  return <nav className="shelf-scopes-region" aria-label="Shelf scopes">
    {scopes.map((scope) => <Button
      key={scope.id}
      type="button"
      aria-current={activeScope === scope.id ? "page" : undefined}
      onClick={() => onScopeChange(scope.id)}
    >{scope.label}</Button>)}
  </nav>;
}
