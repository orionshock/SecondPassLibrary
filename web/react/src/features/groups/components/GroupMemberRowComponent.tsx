import type { GroupMembership } from "@second-pass/spl-api";

import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { Badge } from "../../../components/ui";

export function GroupMemberRowComponent({ membership }: { membership: GroupMembership }) {
  return <div className="group-member-row-component">
    <span className="group-member-row-component__identity">
      <MaterialIcon name="person" />
      &lt;@{membership.user.username}&gt;
    </span>
    {membership.isCurator ? <Badge tone="accent">Curator</Badge> : null}
  </div>;
}
