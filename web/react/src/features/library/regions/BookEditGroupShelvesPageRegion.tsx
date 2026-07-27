import type { ShelfSummary } from "@second-pass/spl-api";
import { Link } from "react-router-dom";

import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, ErrorPanel } from "../../../components/ui";
import { ActionFeedbackComponent } from "../../../shared/feedback/ActionFeedbackComponent";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";

export function BookEditGroupShelvesPageRegion({
  shelves,
  loading,
  error,
  mutation,
  disabled,
  shelfNavigationState,
  onRetry,
  onRemove,
}: {
  shelves: readonly ShelfSummary[];
  loading: boolean;
  error?: Error;
  mutation: MutationState;
  disabled: boolean;
  shelfNavigationState?: (shelf: ShelfSummary) => unknown;
  onRetry: () => void;
  onRemove: (shelf: ShelfSummary) => void;
}) {
  return <section className="book-edit-panel book-edit-group-shelves" aria-labelledby="book-edit-group-shelves-heading">
    <h2 id="book-edit-group-shelves-heading">Group Shelves</h2>
    <p className="book-edit-group-shelves__note">Only group-owned shelves are shown here.</p>
    {loading ? <p className="book-edit-picker-status" aria-busy="true">Loading group shelves...</p> : null}
    {error ? <div className="book-edit-group-shelves__error">
      <ErrorPanel>{error.message}</ErrorPanel>
      <Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button>
    </div> : null}
    {!loading && !error && shelves.length === 0 ? <p className="muted">This book is not on any visible group shelves.</p> : null}
    {!loading && !error && shelves.length > 0 ? <ul className="book-edit-group-shelf-list">
      {shelves.map((shelf) => <li key={shelf.id} className="book-edit-group-shelf-row">
        <div className="book-edit-group-shelf-row__identity">
          <Link to={`/shelves/${encodeURIComponent(shelf.id)}`} state={shelfNavigationState?.(shelf)}>{shelf.name}</Link>
          {shelf.ownerGroup ? <GroupBadgeComponent name={shelf.ownerGroup.name} isPublicGroup={shelf.ownerGroup.isPublicGroup} /> : null}
        </div>
        {shelf.canEdit && shelf.matchedItemId
          ? <RemoveIconButton type="button" label={`Remove ${shelf.name}`} disabled={disabled} onClick={() => onRemove(shelf)} />
          : null}
      </li>)}
    </ul> : null}
    <ActionFeedbackComponent state={mutation} />
  </section>;
}
