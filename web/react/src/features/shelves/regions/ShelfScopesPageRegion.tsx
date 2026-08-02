import type { ShelfScope } from "@second-pass/spl-api";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Button } from "../../../components/ui";

const scopes: Array<{ id: ShelfScope; label: string; icon: string }> = [
  { id: "personal", label: "Personal", icon: "shelves" },
  { id: "shared", label: "Shared by Others", icon: "share" },
  { id: "group", label: "Group Shelves", icon: "group_work" },
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
    ><MaterialIcon name={scope.icon} /><span>{scope.label}</span></Button>)}
  </nav>;
}
