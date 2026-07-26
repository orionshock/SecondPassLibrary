import { Link } from "react-router-dom";
import type { ReactNode } from "react";

import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../books/BookCoverPreviewStripComponent";
import { GroupBadgeComponent } from "../groups/GroupBadgeComponent";
import "./ShelfComponents.css";

export interface ShelfSummaryRowData {
  name: string;
  description: string;
  ownerType: "user" | "group";
  ownerUser: { username: string } | null;
  ownerGroup: { name: string; isPublicGroup: boolean } | null;
  visibility: "private" | "listed";
  itemCount: number;
  canEdit: boolean;
}

export function ShelfSummaryRowComponent({ shelf, detailPath, navigationState, previewBooks = [], actions }: {
  shelf: ShelfSummaryRowData;
  detailPath: string;
  navigationState?: unknown;
  previewBooks?: readonly BookCoverPreviewItem[];
  actions?: ReactNode;
}) {
  const hasPreviews = previewBooks.length > 0;
  return <article className={`shelf-summary-row-component${hasPreviews ? "" : " shelf-summary-row-component--without-previews"}`}>
    <div className="shelf-summary-row-component__identity">
      <div className="shelf-summary-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{shelf.name}</Link></h2>
        {shelf.ownerGroup ? <GroupBadgeComponent
          name={shelf.ownerGroup.name}
          isPublicGroup={shelf.ownerGroup.isPublicGroup}
        /> : null}
      </div>
      {shelf.description ? <p>{shelf.description}</p> : null}
      <div className="shelf-summary-row-component__facts">
        {shelf.ownerType === "user" ? <span>{shelfSummaryOwnerLabel(shelf)}</span> : null}
        {shelf.ownerType === "user" ? <span>{shelf.visibility === "listed" ? "Listed" : "Private"}</span> : null}
        <span>{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
      </div>
      {actions ? <div className="shelf-summary-row-component__actions">{actions}</div> : null}
    </div>
    {hasPreviews ? <BookCoverPreviewStripComponent books={previewBooks} /> : null}
  </article>;
}

export function shelfSummaryOwnerLabel(shelf: ShelfSummaryRowData): string {
  if (shelf.ownerType === "group") return shelf.ownerGroup?.name ?? "Library Group";
  if (shelf.canEdit) return "Personal shelf";
  return shelf.ownerUser ? `Shared by @${shelf.ownerUser.username}` : "Shared shelf";
}
