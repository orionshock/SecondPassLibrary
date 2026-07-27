import { Link } from "react-router-dom";

import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { Badge } from "../../components/ui";
import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../books/BookCoverPreviewStripComponent";
import { GroupBadgeComponent } from "../groups/GroupBadgeComponent";
import "./ShelfComponents.css";

export type ShelfOwnerBadge =
  | { kind: "group"; label: string; isPublicGroup?: boolean }
  | { kind: "user"; label: string };

export function ShelfSummaryRowComponent({ name, description, detailPath, navigationState, previewBooks, owner }: {
  name: string;
  description: string;
  detailPath: string;
  navigationState?: unknown;
  previewBooks: readonly BookCoverPreviewItem[];
  owner?: ShelfOwnerBadge;
}) {
  const hasPreviews = previewBooks.length > 0;
  return <article className={`shelf-summary-row-component${hasPreviews ? "" : " shelf-summary-row-component--without-previews"}`}>
    <div className="shelf-summary-row-component__identity">
      <div className="shelf-summary-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{name}</Link></h2>
        {owner?.kind === "group" ? <GroupBadgeComponent
          name={owner.label}
          isPublicGroup={owner.isPublicGroup}
        /> : null}
        {owner?.kind === "user" ? <Badge>
          <span aria-label={`User: ${owner.label}`}>
            <MaterialIcon name="person" size={15} />
            {owner.label}
          </span>
        </Badge> : null}
      </div>
      {description ? <p>{description}</p> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}
