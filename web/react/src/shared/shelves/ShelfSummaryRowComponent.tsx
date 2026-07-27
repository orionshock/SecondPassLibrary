import { Link } from "react-router-dom";

import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../books/BookCoverPreviewStripComponent";
import { GroupBadgeComponent } from "../groups/GroupBadgeComponent";
import { UserInlineIdentityComponent } from "../users/UserInlineIdentityComponent";
import "./ShelfComponents.css";

export type ShelfOwnerBadge =
  | { kind: "group"; label: string; isPublicGroup?: boolean }
  | { kind: "user"; username: string };

export function ShelfSummaryRowComponent({ name, description, itemCount, detailPath, navigationState, previewBooks, owner }: {
  name: string;
  description: string;
  itemCount: number;
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
        {owner ? <span className="shelf-summary-row-component__owner-relation">
          {owner.kind === "user" ? "shared by" : "from"}
        </span> : null}
        {owner?.kind === "group" ? <GroupBadgeComponent
          name={owner.label}
          isPublicGroup={owner.isPublicGroup}
        /> : null}
        {owner?.kind === "user" ? <UserInlineIdentityComponent username={owner.username} /> : null}
        <span className="shelf-summary-row-component__count">
          ({itemCount} {itemCount === 1 ? "book" : "books"})
        </span>
      </div>
      {description ? <p>{description}</p> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}
