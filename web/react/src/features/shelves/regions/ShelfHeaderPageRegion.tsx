import type { ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { Badge, Button, ErrorPanel, PageHeader } from "../../../components/ui";

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

  return <div className="shelf-detail-header">
    <PageHeader
      title={<span className="page-header__title-content">
      <span>{shelf.name}</span>
      {shelf.ownerGroup?.isPublicGroup ? <Badge tone="success">Public</Badge> : null}
      </span>}
      description={shelf.description || undefined}
      actions={shelf.canEdit && editPath ? <Link className="button-link button--secondary" to={editPath} state={editNavigationState}>Edit Shelf</Link> : undefined}
    />
    <div className="shelf-detail-header__facts">
      <span>{shelfOwnerLabel(shelf)}</span>
      {shelf.ownerType === "user" ? <span>{shelf.visibility === "listed" ? "Listed" : "Private"}</span> : null}
      <span>{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
    </div>
  </div>;
}

function shelfOwnerLabel(shelf: ShelfSummary): string {
  if (shelf.ownerType === "group") return shelf.ownerGroup?.name ?? "Library Group";
  if (shelf.canEdit) return "Personal shelf";
  return shelf.ownerUser ? `Shared by @${shelf.ownerUser.username}` : "Shared shelf";
}
