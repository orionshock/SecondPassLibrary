import type { AssignableGroup, ManagedUserGroup } from "@second-pass/spl-api";
import { useEffect, useState, type FormEvent } from "react";

import { HelpPopoverComponent } from "../../../components/HelpPopoverComponent";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button } from "../../../components/ui";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { ActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import { GroupBadgeComponent } from "../../../shared/groups/GroupBadgeComponent";

export function UserGroupMembershipsPageRegion({ memberships, assignableGroups, state, onAdd, onRemove, onCuratorChange }: {
  memberships: readonly ManagedUserGroup[];
  assignableGroups: readonly AssignableGroup[];
  state: MutationState;
  onAdd: (groupId: string, isCurator: boolean) => void;
  onRemove: (membership: ManagedUserGroup) => void;
  onCuratorChange: (membership: ManagedUserGroup, isCurator: boolean) => void;
}) {
  const [groupId, setGroupId] = useState(assignableGroups[0]?.id ?? "");
  const [isCurator, setIsCurator] = useState(false);
  const selectedGroup = assignableGroups.find(({ id }) => id === groupId);
  useEffect(() => { if (!assignableGroups.some(({ id }) => id === groupId)) setGroupId(assignableGroups[0]?.id ?? ""); }, [assignableGroups, groupId]);
  useEffect(() => { if (selectedGroup?.isPublicGroup && isCurator) setIsCurator(false); }, [isCurator, selectedGroup?.isPublicGroup]);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (groupId) onAdd(groupId, curatorValueForGroup(selectedGroup, isCurator));
  }

  return <section className="user-edit-region" aria-labelledby="group-memberships-heading">
    <h2 id="group-memberships-heading">Group memberships</h2>
    <div className="user-membership-list">
      {memberships.map((membership) => {
        const removeEnabled = canRemoveMembership(membership, memberships.length);
        return <div className="user-membership-row" key={membership.id}>
          <div className="user-membership-left">
            <RemoveIconButton label={`Remove ${membership.name}`} disabled={!removeEnabled} onClick={() => onRemove(membership)} />
            <GroupBadgeComponent name={membership.name} isPublicGroup={membership.isPublicGroup} />
          </div>
          <div className="user-membership-curator">
            {membership.isPublicGroup
              ? <span className="user-membership-public-label">Public Group <HelpPopoverComponent ariaLabel="Public Group curator help" icon="help" mouseoverText="Only Librarians/Managers may Curate the Public Group" /></span>
              : <label><input type="checkbox" checked={membership.isCurator} onChange={(event) => onCuratorChange(membership, event.target.checked)} /> Curator</label>}
          </div>
        </div>;
      })}
    </div>
    <form className="user-membership-add" onSubmit={submit}>
      <h3>Add to group</h3>
      {assignableGroups.length ? <>
        <div className="form-field"><label htmlFor="managed-user-add-group">Group</label><select id="managed-user-add-group" value={groupId} onChange={(event) => setGroupId(event.target.value)}>{assignableGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}</select></div>
        <div className="form-field"><span>Curator</span>{selectedGroup?.isPublicGroup ? <span className="muted">Public membership cannot be curator.</span> : <label className="checkbox-control"><input type="checkbox" checked={isCurator} onChange={(event) => setIsCurator(event.target.checked)} /> Grant curator access</label>}</div>
      </> : <p className="muted">No groups are available to add.</p>}
      <ActionRowComponent state={state}><Button type="submit" disabled={!groupId || state.pending}>{state.pending ? "Adding..." : "Add"}</Button></ActionRowComponent>
    </form>
  </section>;
}

export function canRemoveMembership(membership: ManagedUserGroup, membershipCount: number): boolean {
  return !membership.isPublicGroup || membershipCount > 1;
}

export function curatorValueForGroup(group: AssignableGroup | undefined, requested: boolean): boolean {
  return group?.isPublicGroup ? false : requested;
}
