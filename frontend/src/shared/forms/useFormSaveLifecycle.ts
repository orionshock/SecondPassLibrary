import { useCallback, useEffect, useRef, useState, type Dispatch, type SetStateAction } from "react";
import { useBlocker } from "react-router";

import type { MutationState } from "../feedback/mutationState";
import { useAutoDismissMutationMessage } from "../feedback/useAutoDismissMutationMessage";

type DraftUpdate<Draft> = Draft | ((current: Draft) => Draft);
type MutationFeedback = Omit<MutationState, "pending">;

export function useFormSaveLifecycle<Draft>({
  initialDraft,
  draftsEqual,
  discardMessage,
  initialFeedback = {},
}: {
  initialDraft: Draft;
  draftsEqual: (draft: Draft, baseline: Draft) => boolean;
  discardMessage: string;
  initialFeedback?: MutationFeedback;
}) {
  const [draft, setDraft] = useState(initialDraft);
  const [baseline, setBaseline] = useState(initialDraft);
  const [pending, setPending] = useState(false);
  const pendingRef = useRef(false);
  const [feedback, setFeedback] = useState<MutationFeedback>(initialFeedback);
  const allowNavigation = useRef(false);
  const dirty = !draftsEqual(draft, baseline);
  const navigationBlocked = dirty || pending;
  const mutation: MutationState = { pending, ...feedback };
  const setMutationFeedback = useCallback<Dispatch<SetStateAction<MutationState>>>((next) => {
    setFeedback((current) => {
      const resolved = typeof next === "function"
        ? next({ pending: pendingRef.current, ...current })
        : next;
      return { message: resolved.message, error: resolved.error };
    });
  }, []);
  useAutoDismissMutationMessage(mutation, setMutationFeedback);

  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current
    && navigationBlocked
    && currentLocation.pathname !== nextLocation.pathname
  ));

  useEffect(() => {
    const preventUnload = (event: BeforeUnloadEvent) => {
      if (navigationBlocked) event.preventDefault();
    };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [navigationBlocked]);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (pendingRef.current) {
      blocker.reset();
      return;
    }
    if (window.confirm(discardMessage)) blocker.proceed();
    else blocker.reset();
  }, [blocker, discardMessage]);

  const changeDraft = useCallback((update: DraftUpdate<Draft>): boolean => {
    if (pendingRef.current) return false;
    setDraft((current) => typeof update === "function"
      ? (update as (value: Draft) => Draft)(current)
      : update);
    setFeedback({});
    return true;
  }, []);

  const loadDraft = useCallback((next: Draft) => {
    pendingRef.current = false;
    setPending(false);
    setDraft(next);
    setBaseline(next);
  }, []);

  const beginSave = useCallback((): boolean => {
    if (pendingRef.current) return false;
    pendingRef.current = true;
    setPending(true);
    setFeedback({});
    return true;
  }, []);

  const saveSucceeded = useCallback((next: Draft, message?: string) => {
    pendingRef.current = false;
    setDraft(next);
    setBaseline(next);
    setPending(false);
    setFeedback(message ? { message } : {});
  }, []);

  const saveFailed = useCallback((error: Error) => {
    pendingRef.current = false;
    setPending(false);
    setFeedback({ error });
  }, []);

  const setError = useCallback((error: Error) => {
    if (pendingRef.current) return;
    setFeedback({ error });
  }, []);

  function confirmDiscard(): boolean {
    if (pendingRef.current) return false;
    if (dirty && !window.confirm(discardMessage)) return false;
    allowNavigation.current = true;
    return true;
  }

  const permitNavigation = useCallback(() => {
    allowNavigation.current = true;
  }, []);

  const protectNavigation = useCallback(() => {
    allowNavigation.current = false;
  }, []);

  return {
    draft,
    dirty,
    mutation,
    changeDraft,
    loadDraft,
    beginSave,
    saveSucceeded,
    saveFailed,
    setError,
    confirmDiscard,
    permitNavigation,
    protectNavigation,
  };
}
