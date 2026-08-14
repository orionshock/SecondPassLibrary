import type { BookGroupSummary, LibraryGroup } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router";

import { AddIconButton } from "../../../components/icons/AddIconButton";
import { MaterialIcon } from "../../../components/icons/MaterialIcon";
import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import { ActionFeedback } from "../../../shared/feedback/ActionFeedback";
import type { MutationState } from "../../../shared/feedback/mutationState";

export function BookEditGroupsPageRegion({
  currentGroups,
  availableGroups,
  loading,
  pickerError,
  mutation,
  disabled,
  groupNavigationState,
  onRetry,
  onSelectionChange,
  onAdd,
  onRemove,
}: {
  currentGroups: readonly BookGroupSummary[];
  availableGroups: readonly LibraryGroup[];
  loading: boolean;
  pickerError?: Error;
  mutation: MutationState;
  disabled: boolean;
  groupNavigationState?: (group: BookGroupSummary) => unknown;
  onRetry: () => void;
  onSelectionChange: () => void;
  onAdd: (groupId: string) => void;
  onRemove: (group: BookGroupSummary) => void;
}) {
  const unassignedGroups = useMemo(
    () => availableGroups.filter((group) => !currentGroups.some(({ id }) => id === group.id)),
    [availableGroups, currentGroups],
  );
  const [groupId, setGroupId] = useState("");

  useEffect(() => {
    if (!unassignedGroups.some(({ id }) => id === groupId)) setGroupId(unassignedGroups[0]?.id ?? "");
  }, [groupId, unassignedGroups]);

  const solePublicId = currentGroups.length === 1 && currentGroups[0]?.isPublicGroup
    ? currentGroups[0].id
    : undefined;

  return <section className="book-edit-panel book-edit-groups" aria-labelledby="book-edit-groups-heading">
    <h2 id="book-edit-groups-heading">Library Groups</h2>
    <ul className="book-edit-group-list">
      {currentGroups.map((group) => <li key={group.id} className="book-edit-group-row">
        <Link
          className={group.isPublicGroup ? "book-edit-group-assignment book-edit-group-assignment--public" : "book-edit-group-assignment"}
          to={`/groups/${encodeURIComponent(group.id)}`}
          state={groupNavigationState?.(group)}
          title={group.description || undefined}
        >
          <MaterialIcon name={group.isPublicGroup ? "public" : "group"} size={17} />
          <span>{group.name}</span>
        </Link>
        {group.id !== solePublicId
          ? <RemoveIconButton type="button" label={`Remove ${group.name}`} disabled={disabled} onClick={() => onRemove(group)} />
          : <span className="book-edit-group-row__control-spacer" aria-hidden="true" />}
      </li>)}
    </ul>

    <div className="book-edit-group-add">
      <label htmlFor="book-edit-add-group">Add to group</label>
      {loading ? <span className="book-edit-picker-status">Loading groups...</span> : null}
      {pickerError ? <ErrorPanel><span>Groups could not be loaded.</span> <Button type="button" size="small" tone="secondary" onClick={onRetry}>Retry</Button></ErrorPanel> : null}
      {!loading && !pickerError ? <div className="book-edit-inline-control">
        <select id="book-edit-add-group" value={groupId} disabled={disabled || unassignedGroups.length === 0} onChange={(event) => { setGroupId(event.target.value); onSelectionChange(); }}>
          {unassignedGroups.length === 0 ? <option value="">No groups available</option> : null}
          {unassignedGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
        </select>
        <AddIconButton type="button" label="Add group" disabled={disabled || !groupId} onClick={() => onAdd(groupId)} />
      </div> : null}
    </div>
    <ActionFeedback state={mutation} />
  </section>;
}
