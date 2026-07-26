import type { GroupMembership } from "@second-pass/spl-api";
import type { ReactNode } from "react";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge } from "../../../components/ui";

export function GroupMemberRowComponent({ membership, actions }: { membership: GroupMembership; actions?: ReactNode }) {
  return <div className="group-member-row-component">
    <span className="group-member-row-component__identity">
      <MaterialIcon name="person" />
      &lt;@{membership.user.username}&gt;
    </span>
    <span className="group-member-row-component__status">
      {membership.isCurator ? <Badge tone="accent">Curator</Badge> : null}
      {actions}
    </span>
  </div>;
}
