import type { ReactNode } from "react";

import { Button } from "../../components/ui";
import { ActionFeedbackComponent } from "../feedback/ActionFeedbackComponent";
import type { MutationState } from "../feedback/mutationState";

export function ActionRowComponent({ state, children }: { state: MutationState; children: ReactNode }) {
  return <div className="form-action-row"><ActionFeedbackComponent state={state} /><div className="form-actions">{children}</div></div>;
}

export function SaveCancelActionRowComponent({ state, submitLabel, pendingLabel, onCancel }: {
  state: MutationState;
  submitLabel: string;
  pendingLabel: string;
  onCancel: () => void;
}) {
  return <ActionRowComponent state={state}>
    <Button type="button" className="button--secondary" disabled={state.pending} onClick={onCancel}>Cancel</Button>
    <Button type="submit" disabled={state.pending}>{state.pending ? pendingLabel : submitLabel}</Button>
  </ActionRowComponent>;
}
