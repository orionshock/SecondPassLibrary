import type { GroupMembership, Page } from "@second-pass/spl-api";

import { Button, ErrorPanel } from "../../../components/ui";
import { PagerComponent } from "../../../shared/pagination/PagerComponent";
import { GroupMemberRowComponent } from "../components/GroupMemberRowComponent";

export function GroupMembersPageRegion({ page, pageNumber, pageSize, loading, error, onPageChange, onPageSizeChange, onRetry }: {
  page?: Page<GroupMembership>;
  pageNumber: number;
  pageSize: number;
  loading: boolean;
  error?: Error;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  onRetry: () => void;
}) {
  if (!page && loading) return <section className="group-detail-state" aria-live="polite" aria-busy="true">Loading members...</section>;
  if (!page && error) return <section className="group-detail-state"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></section>;
  if (!page) return null;

  return <section className={`group-members-region${loading ? " group-results--loading" : ""}`} aria-label="Group members" aria-busy={loading}>
    {error ? <div className="groups-inline-error"><ErrorPanel>{error.message}</ErrorPanel><Button type="button" onClick={onRetry}>Retry</Button></div> : null}
    {page.items.length === 0 ? <p className="group-detail-state muted">No members are visible.</p> : <div className="group-member-rows">
      {page.items.map((membership) => <GroupMemberRowComponent key={membership.user.profileId} membership={membership} />)}
    </div>}
    <PagerComponent
      page={pageNumber}
      pageSize={pageSize}
      count={page.count}
      hasPrevious={Boolean(page.previous)}
      hasNext={Boolean(page.next)}
      itemLabel="Members"
      onPageChange={onPageChange}
      onPageSizeChange={onPageSizeChange}
    />
  </section>;
}
