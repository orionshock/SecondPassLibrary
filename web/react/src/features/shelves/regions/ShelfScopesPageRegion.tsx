import type { ShelfScope } from "@second-pass/spl-api";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button } from "../../../components/ui";
import { shelfScopePresentations } from "../shelfScopes";

export function ShelfScopesPageRegion({ activeScope, onScopeChange }: {
  activeScope: ShelfScope;
  onScopeChange: (scope: ShelfScope) => void;
}) {
  return <nav className="shelf-scopes-region" aria-label="Shelf scopes">
    {shelfScopePresentations.map((scope) => <Button
      key={scope.id}
      type="button"
      aria-current={activeScope === scope.id ? "page" : undefined}
      onClick={() => onScopeChange(scope.id)}
    ><MaterialIcon name={scope.materialIcon} /><span>{scope.label}</span></Button>)}
  </nav>;
}
