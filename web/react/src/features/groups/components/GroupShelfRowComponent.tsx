import type { ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";

export function GroupShelfRowComponent({ shelf, detailPath, navigationState }: {
  shelf: ShelfSummary;
  detailPath: string;
  navigationState?: unknown;
}) {
  return <article className="group-shelf-row-component">
    <div className="group-shelf-row-component__title">
      <h2><Link to={detailPath} state={navigationState}>{shelf.name}</Link></h2>
      {shelf.ownerGroup ? <GroupBadgeComponent
        name={shelf.ownerGroup.name}
        isPublicGroup={shelf.ownerGroup.isPublicGroup}
      /> : null}
    </div>
    {shelf.description ? <p>{shelf.description}</p> : null}
    <span className="muted">{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
  </article>;
}
