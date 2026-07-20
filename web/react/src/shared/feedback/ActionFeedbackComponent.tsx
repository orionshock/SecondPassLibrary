import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { ErrorPanel } from "../../components/ui";
import type { MutationState } from "./mutationState";

export function ActionFeedbackComponent({ state }: { state: MutationState }) {
  return <div className={`action-feedback${state.error ? " action-feedback--error" : state.message ? " action-feedback--success" : ""}`}>
    {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
    {state.message ? <span className="success-message" role="status"><MaterialIcon name="check_circle" className="success-icon" />{state.message}</span> : null}
  </div>;
}
