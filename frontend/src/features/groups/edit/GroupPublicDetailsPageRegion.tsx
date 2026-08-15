import type { LibraryGroup } from "@second-pass/spl-api";

import { GroupBadge } from "../../../shared/groups/GroupBadge";

export function GroupPublicDetailsPageRegion({ group }: { group: LibraryGroup }) {
  return <section className="group-edit-section-state" aria-label="Public group details">
    <GroupBadge name={group.name} isPublicGroup />
    {group.description ? <p>{group.description}</p> : null}
    <p className="muted">Public group identity is managed in Server Settings.</p>
  </section>;
}
