import type { ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel } from "../../../components/ui";

export function ShelfHeaderPageRegion({ shelf, loading, error, editPath, editNavigationState, onRetry }: {
  shelf?: ShelfSummary;
  loading: boolean;
  error?: Error;
  editPath?: string;
  editNavigationState?: unknown;
  onRetry: () => void;
}) {
  if (!shelf && loading) return <section className="shelf-detail-state" aria-live="polite" aria-busy="true">Loading shelf...</section>;
  if (!shelf && error) return <section className="shelf-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!shelf) return null;

  return <header className="shelf-detail-header">
    <div className="shelf-detail-header__title">
      <h1>{shelf.name}</h1>
      {shelf.ownerGroup?.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
    </div>
    {shelf.description ? <p>{shelf.description}</p> : null}
    <div className="shelf-detail-header__facts">
      <span>{shelfOwnerLabel(shelf)}</span>
      {shelf.ownerType === "user" ? <span>{shelf.visibility === "listed" ? "Listed" : "Private"}</span> : null}
      <span>{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
    </div>
    {shelf.canEdit && editPath ? <Link className="button-link button--secondary shelf-detail-header__edit" to={editPath} state={editNavigationState}>Edit Shelf</Link> : null}
  </header>;
}

function shelfOwnerLabel(shelf: ShelfSummary): string {
  if (shelf.ownerType === "group") return shelf.ownerGroup?.name ?? "Library Group";
  if (shelf.canEdit) return "Personal shelf";
  return shelf.ownerUser ? `Shared by @${shelf.ownerUser.username}` : "Shared shelf";
}
