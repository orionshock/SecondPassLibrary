import type { AssignableGroup, ManagedUserGroup } from "@second-pass/spl-api";
import { useEffect, useState, type FormEvent } from "react";

import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Badge, Button } from "../../../components/ui";
import { ActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import type { MutationState } from "../../../shared/feedback/mutationState";

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
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); if (groupId) onAdd(groupId, selectedGroup?.isPublicGroup ? false : isCurator); }

  return <section className="user-edit-region" aria-labelledby="group-memberships-heading">
    <h2 id="group-memberships-heading">Group memberships</h2>
    <div className="user-membership-list">
      {memberships.map((membership) => <div className="user-membership-row" key={membership.id}>
        <div>{membership.isPublicGroup ? null : <RemoveIconButton label={`Remove ${membership.name}`} onClick={() => onRemove(membership)} />}</div>
        <div className="user-membership-name"><Badge tone={membership.isPublicGroup ? "accent" : "default"}>{membership.name}</Badge>{membership.isPublicGroup ? <span className="muted">Public Group</span> : null}</div>
        <div className="user-membership-curator">{membership.isPublicGroup ? <span className="muted">Available to everyone</span> : <label><input type="checkbox" checked={membership.isCurator} onChange={(event) => onCuratorChange(membership, event.target.checked)} /> Curator</label>}</div>
      </div>)}
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
