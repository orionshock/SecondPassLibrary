import type { ShelfScope } from "@second-pass/spl-api";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button } from "../../../components/UiPrimitives";
import { shelfScopePresentations } from "../shelfScopes";

export function ShelfScopesPageRegion({ activeScope, onScopeChange }: {
  activeScope: ShelfScope;
  onScopeChange: (scope: ShelfScope) => void;
}) {
  return <div className="shelf-scopes-region" role="group" aria-label="Shelf scopes">
    {shelfScopePresentations.map((scope) => <Button
      key={scope.id}
      type="button"
      aria-pressed={activeScope === scope.id}
      onClick={() => onScopeChange(scope.id)}
    ><MaterialIcon name={scope.materialIcon} /><span>{scope.label}</span></Button>)}
  </div>;
}
