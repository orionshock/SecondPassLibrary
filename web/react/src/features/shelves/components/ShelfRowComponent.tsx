import type { ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge } from "../../../components/ui";
import { BookCoverPreviewStripComponent, type BookCoverPreviewItem } from "../../../shared/books/BookCoverPreviewStripComponent";

export function ShelfRowComponent({ shelf, detailPath, navigationState, previewBooks, editPath, editNavigationState }: {
  shelf: ShelfSummary;
  detailPath: string;
  navigationState?: unknown;
  previewBooks: readonly BookCoverPreviewItem[];
  editPath?: string;
  editNavigationState?: unknown;
}) {
  return <article className="shelf-row-component">
    <div className="shelf-row-component__identity">
      <div className="shelf-row-component__title">
        <h2><Link to={detailPath} state={navigationState}>{shelf.name}</Link></h2>
        {shelf.ownerGroup?.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
      </div>
      {shelf.description ? <p>{shelf.description}</p> : null}
      <div className="shelf-row-component__facts">
        <span>{ownerLabel(shelf)}</span>
        {shelf.ownerType === "user" ? <span>{shelf.visibility === "listed" ? "Listed" : "Private"}</span> : null}
        <span>{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
      </div>
      {shelf.canEdit && editPath ? <Link className="shelf-row-component__edit" to={editPath} state={editNavigationState}>Edit</Link> : null}
    </div>
    <BookCoverPreviewStripComponent books={previewBooks} />
  </article>;
}

export function shelfOwnerLabel(shelf: ShelfSummary): string {
  return ownerLabel(shelf);
}

function ownerLabel(shelf: ShelfSummary): string {
  if (shelf.ownerType === "group") return shelf.ownerGroup?.name ?? "Library Group";
  if (shelf.canEdit) return "Personal shelf";
  return shelf.ownerUser ? `Shared by @${shelf.ownerUser.username}` : "Shared shelf";
}
