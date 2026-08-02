import type { ReactNode } from "react";
import { Link } from "react-router";

import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../books/BookCoverPreviewStripComponent";
import { GroupBadgeComponent } from "../groups/GroupBadgeComponent";
import { UserInlineIdentityComponent } from "../users/UserInlineIdentityComponent";
import "./ShelfComponents.css";

export type ShelfOwnerBadge =
  | { kind: "group"; label: string; isPublicGroup?: boolean }
  | { kind: "user"; username: string };

export function ShelfSummaryRowComponent({ name, description, itemCount, detailPath, navigationState, previewBooks, owner, actions }: {
  name: string;
  description: string;
  itemCount: number;
  detailPath: string;
  navigationState?: unknown;
  previewBooks: readonly BookCoverPreviewItem[];
  owner?: ShelfOwnerBadge;
  actions?: ReactNode;
}) {
  const hasPreviews = previewBooks.length > 0;
  return <article className={`shelf-summary-row-component${hasPreviews ? "" : " shelf-summary-row-component--without-previews"}`}>
    <div className="shelf-summary-row-component__identity">
      <div className="shelf-summary-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{name}</Link></h2>
        <span className="css-dot" aria-hidden="true" />
        {owner ? <span className="shelf-summary-row-component__owner-relation">
          {owner.kind === "user" ? "shared by" : "from"}
        </span> : null}
        {owner?.kind === "group" ? <GroupBadgeComponent
          name={owner.label}
          isPublicGroup={owner.isPublicGroup}
        /> : null}
        {owner?.kind === "user" ? <UserInlineIdentityComponent username={owner.username} /> : null}
        {owner ? <span className="css-dot" aria-hidden="true" /> : null}
        <span className="shelf-summary-row-component__count">
          {itemCount} {itemCount === 1 ? "book" : "books"}
        </span>
        {actions ? <span className="shelf-summary-row-component__actions">{actions}</span> : null}
      </div>
      {description ? <p>{description}</p> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}
