import { Button, ErrorPanel } from "../../../components/ui";
import type { MutationState } from "../../../shared/feedback/mutationState";

export function GroupDangerZonePageRegion({ state, controlsDisabled, onDelete }: {
  state: MutationState;
  controlsDisabled?: boolean;
  onDelete: () => void;
}) {
  return <section className="group-danger-zone" aria-labelledby="group-delete-heading">
    <div>
      <h2 id="group-delete-heading">Delete Group</h2>
      <p>Removes memberships, Book assignments, and Group-owned Shelves. Users, Books, and files are not deleted.</p>
      {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
    </div>
    <Button type="button" tone="danger" disabled={controlsDisabled || state.pending} onClick={onDelete}>
      {state.pending ? "Deleting..." : "Delete Group"}
    </Button>
  </section>;
}
