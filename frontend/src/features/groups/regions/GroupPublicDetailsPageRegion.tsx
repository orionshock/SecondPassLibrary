import type { LibraryGroup } from "@second-pass/spl-api";

import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";

export function GroupPublicDetailsPageRegion({ group }: { group: LibraryGroup }) {
  return <section className="group-edit-section-state" aria-label="Public group details">
    <GroupBadgeComponent name={group.name} isPublicGroup />
    {group.description ? <p>{group.description}</p> : null}
    <p className="muted">Public group identity is managed in Server Settings.</p>
  </section>;
}
