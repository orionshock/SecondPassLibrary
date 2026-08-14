import type { CurrentUser } from "@second-pass/spl-api";

import { Badge, Surface } from "../../../components/UiPrimitives";
import { GroupBadge } from "../../../shared/groups/GroupBadge";

export function GroupMembershipsPageRegion({ user, advancedGroupsEnabled }: { user: CurrentUser; advancedGroupsEnabled: boolean }) {
  if (!advancedGroupsEnabled) return null;
  return <Surface title="Group memberships"><div className="item-list profile-group-memberships">
    {user.groups.map((group) => <div className="profile-group-membership-row" key={group.id}>
      <span className="profile-group-membership-identity"><GroupBadge name={group.name} isPublicGroup={group.isPublicGroup} /></span>
      <span className="profile-group-membership-status">{group.isCurator ? <Badge tone="accent">Curator</Badge> : null}</span>
    </div>)}
    {user.groups.length === 0 ? <p className="muted">No group memberships.</p> : null}
  </div></Surface>;
}
