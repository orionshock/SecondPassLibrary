import type { ReactNode } from "react";

import { Button } from "../../components/UiPrimitives";
import { ActionFeedback } from "../feedback/ActionFeedback";
import type { MutationState } from "../feedback/mutationState";

export function ActionRow({ state, children }: { state: MutationState; children: ReactNode }) {
  return <div className="form-action-row"><ActionFeedback state={state} /><div className="form-actions">{children}</div></div>;
}

export function SaveCancelActionRow({ state, submitLabel, pendingLabel, disabled = false, onCancel }: {
  state: MutationState;
  submitLabel: string;
  pendingLabel: string;
  disabled?: boolean;
  onCancel: () => void;
}) {
  return <ActionRow state={state}>
    <Button type="button" tone="secondary" disabled={state.pending || disabled} onClick={onCancel}>Cancel</Button>
    <Button type="submit" disabled={state.pending || disabled}>{state.pending ? pendingLabel : submitLabel}</Button>
  </ActionRow>;
}
