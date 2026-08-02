import type { GroupMembership, Page } from "@second-pass/spl-api";

import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, ErrorPanel } from "../../../components/ui";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { GroupMemberRowComponent } from "../components/GroupMemberRowComponent";

export function GroupMembersEditPageRegion({ page, pageNumber, pageSize, isPublicGroup, loading, error, pendingProfileId, controlsDisabled, onToggleCurator, onRemove, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<GroupMembership>;
  pageNumber: number;
  pageSize: number;
  isPublicGroup: boolean;
  loading: boolean;
  error?: Error;
  pendingProfileId?: string;
  controlsDisabled?: boolean;
  onToggleCurator: (membership: GroupMembership) => void;
  onRemove: (membership: GroupMembership) => void;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="group-edit-section-state" aria-live="polite" aria-busy="true">Loading members...</section>;
  if (!page && error) return <section className="group-edit-section-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className="group-members-edit-region" aria-label="Current group members" aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="muted">This group has no members.</p> : <div className="group-member-rows">
      {page.items.map((membership) => <GroupMemberRowComponent
        key={membership.user.profileId}
        membership={membership}
        actions={<>
          {!isPublicGroup ? <Button
            type="button"
            className="button--secondary"
            disabled={controlsDisabled || Boolean(pendingProfileId)}
            onClick={() => onToggleCurator(membership)}
          >{membership.isCurator ? "Remove curator" : "Make curator"}</Button> : null}
          <RemoveIconButton
            type="button"
            label={`Remove ${membership.user.username} from group`}
            title={pendingProfileId === membership.user.profileId ? "Removing" : "Remove member"}
            disabled={controlsDisabled || Boolean(pendingProfileId)}
            onClick={() => onRemove(membership)}
          />
        </>}
      />)}
    </div>}
    <PagerComponent page={pageNumber} pageSize={pageSize} count={page.count} hasPrevious={Boolean(page.previous)} hasNext={Boolean(page.next)} itemLabel="Members" onPageChange={onPageChange} onPageSizeChange={onPageSizeChange} />
  </section>;
}
