import { Button, ErrorPanel } from "../../../components/ui";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { titleKind, type LibraryEntityKind } from "../authorSeriesLifecycle";

export function AuthorSeriesDangerZonePageRegion({
  kind,
  name,
  bookCount,
  state,
  controlsDisabled = false,
  onDelete,
}: {
  kind: LibraryEntityKind;
  name: string;
  bookCount: number;
  state: MutationState;
  controlsDisabled?: boolean;
  onDelete: () => void;
}) {
  const entity = titleKind(kind);
  const attached = bookCount > 0;
  const reasonId = `${kind}-delete-availability`;

  return <section className="author-series-danger-zone" aria-labelledby={`${kind}-delete-heading`}>
    <div>
      <h2 id={`${kind}-delete-heading`}>Delete {entity}</h2>
      <p>Deletion is permanent and removes the {entity} catalog record itself.</p>
      <p>Books are never detached, reassigned, or merged. Deletion is available only when no Books are attached.</p>
      <p id={reasonId} className={attached ? "author-series-danger-zone__blocked" : "muted"}>
        {attached
          ? `${entity} cannot be deleted because ${bookCount} ${bookCount === 1 ? "Book is" : "Books are"} attached.`
          : `No Books are attached to ${name}. Deletion is available.`}
      </p>
      {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
    </div>
    <Button
      type="button"
      tone="danger"
      disabled={attached || controlsDisabled || state.pending}
      aria-describedby={reasonId}
      onClick={onDelete}
    >
      {state.pending ? "Deleting..." : `Delete ${entity}`}
    </Button>
  </section>;
}
