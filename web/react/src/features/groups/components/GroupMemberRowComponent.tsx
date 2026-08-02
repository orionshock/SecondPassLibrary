import type { GroupMembership } from "@second-pass/spl-api";
import type { ReactNode } from "react";

import { Badge } from "../../../components/ui";
import { UserInlineIdentityComponent } from "../../../shared/users/UserInlineIdentityComponent";

export function GroupMemberRowComponent({ membership, actions }: { membership: GroupMembership; actions?: ReactNode }) {
  return <div className="group-member-row-component">
    <span className="group-member-row-component__identity">
      <UserInlineIdentityComponent username={membership.user.username} />
    </span>
    <span className="group-member-row-component__status">
      {membership.isCurator ? <Badge tone="accent">Curator</Badge> : null}
      {actions}
    </span>
  </div>;
}
