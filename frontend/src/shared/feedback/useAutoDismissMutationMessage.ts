import { useEffect, type Dispatch, type SetStateAction } from "react";

export const SUCCESS_MESSAGE_TIMEOUT_MS = 5000;

export function clearMatchingMutationMessage<T extends { message?: string }>(state: T, message: string): T {
  return state.message === message ? { ...state, message: undefined } : state;
}

export function useAutoDismissMutationMessage<T extends { message?: string }>(
  state: T,
  setState: Dispatch<SetStateAction<T>>,
): void {
  useEffect(() => {
    if (!state.message) return;
    const message = state.message;
    const timeout = window.setTimeout(() => {
      setState((current) => clearMatchingMutationMessage(current, message));
    }, SUCCESS_MESSAGE_TIMEOUT_MS);
    return () => window.clearTimeout(timeout);
  }, [setState, state.message]);
}
