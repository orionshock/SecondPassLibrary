import { useEffect, useState } from "react";

import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { ErrorPanel } from "../../components/UiPrimitives";
import type { MutationState } from "./mutationState";
import { SUCCESS_MESSAGE_TIMEOUT_MS } from "./useAutoDismissMutationMessage";

export function ActionFeedback({ state }: { state: MutationState }) {
  const [visibleMessage, setVisibleMessage] = useState(state.message);

  useEffect(() => {
    setVisibleMessage(state.message);
    if (!state.message) return;
    const timeout = window.setTimeout(() => setVisibleMessage(undefined), SUCCESS_MESSAGE_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [state.message]);

  return <div className={`action-feedback${state.error ? " action-feedback--error" : visibleMessage ? " action-feedback--success" : ""}`}>
    {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
    {visibleMessage ? <span className="success-message" role="status"><MaterialIcon name="check_circle" className="success-icon" />{visibleMessage}</span> : null}
  </div>;
}
