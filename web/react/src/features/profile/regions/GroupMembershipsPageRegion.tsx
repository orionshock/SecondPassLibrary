import type { CurrentUser } from "@second-pass/spl-api";

import { Badge, Surface } from "../../../components/ui";
import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";

export function GroupMembershipsPageRegion({ user }: { user: CurrentUser }) {
  if (!user.advancedLibraryGroupsEnabled) return null;
  return <Surface title="Group memberships"><div className="item-list profile-group-memberships">
    {user.groups.map((group) => <div className="profile-group-membership-row" key={group.id}>
      <span className="profile-group-membership-identity"><GroupBadgeComponent name={group.name} isPublicGroup={group.isPublicGroup} /></span>
      <span className="profile-group-membership-status">{group.isCurator ? <Badge tone="accent">Curator</Badge> : null}</span>
    </div>)}
    {user.groups.length === 0 ? <p className="muted">No group memberships.</p> : null}
  </div></Surface>;
}
