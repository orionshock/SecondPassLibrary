import type { ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router";

import { Badge, Button, ErrorPanel, PageHeader } from "../../../components/UiPrimitives";
import { UserInlineIdentity } from "../../../shared/users/UserInlineIdentity";

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
      <ShelfOwnerIdentity shelf={shelf} />
      {shelf.ownerType === "user" ? <span>{shelf.visibility === "listed" ? "Listed" : "Private"}</span> : null}
      <span>{shelf.itemCount} {shelf.itemCount === 1 ? "item" : "items"}</span>
    </div>
  </div>;
}

function ShelfOwnerIdentity({ shelf }: { shelf: ShelfSummary }) {
  if (shelf.ownerType === "group") return <span>{shelf.ownerGroup?.name ?? "Library Group"}</span>;
  if (shelf.canEdit) return <span>Personal shelf</span>;
  return shelf.ownerUser
    ? <span>Shared by <UserInlineIdentity username={shelf.ownerUser.username} /></span>
    : <span>Shared shelf</span>;
}
