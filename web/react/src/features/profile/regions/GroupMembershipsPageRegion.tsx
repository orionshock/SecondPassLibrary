import type { CurrentUser } from "@second-pass/spl-api";

import { Badge, Surface } from "../../../components/ui";
import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";

export function GroupMembershipsPageRegion({ user }: { user: CurrentUser }) {
  if (!user.advancedLibraryGroupsEnabled) return null;
  return <Surface title="Group memberships"><div className="item-list">
    {user.groups.map((group) => <div className="item-row" key={group.id}>
      <GroupBadgeComponent name={group.name} isPublicGroup={group.isPublicGroup} />
      <span className="item-badges">{group.isCurator ? <Badge tone="accent">Curator</Badge> : <Badge>Member</Badge>}</span>
    </div>)}
    {user.groups.length === 0 ? <p className="muted">No group memberships.</p> : null}
  </div></Surface>;
}
