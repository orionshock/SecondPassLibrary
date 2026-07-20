import type { CurrentUser } from "@second-pass/spl-api";

import { Badge, Surface } from "../../../components/ui";

export function GroupMembershipsPageRegion({ user }: { user: CurrentUser }) {
  if (!user.advancedLibraryGroupsEnabled) return null;
  return <Surface title="Group memberships"><div className="item-list">
    {user.groups.map((group) => <div className="item-row" key={group.id}><span>{group.name}</span><span className="item-badges">{group.isPublicGroup ? <Badge>Public</Badge> : null}{group.isCurator ? <Badge tone="accent">Curator</Badge> : <Badge>Member</Badge>}</span></div>)}
    {user.groups.length === 0 ? <p className="muted">No group memberships.</p> : null}
  </div></Surface>;
}
