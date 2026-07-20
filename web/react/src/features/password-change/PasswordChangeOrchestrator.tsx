import { changeCurrentUserPassword } from "@second-pass/spl-api";
import { useReducer, useState, type FormEvent } from "react";
import { useNavigate, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { idleMutationState, normalizeMutationError, type MutationState } from "../../shared/feedback/mutationState";
import { passwordBreadcrumbFallback } from "../profile/profileBreadcrumbs";
import "../../shared/layout/AccountPageLayout.css";
import { PasswordChangePageRegion } from "./regions/PasswordChangePageRegion";
import { emptyPasswordDraft, passwordConfirmationError, passwordDraftReducer } from "./passwordChangeForm";
import "./PasswordChange.css";

export function PasswordChangeOrchestrator() {
  const { currentUser, refreshCurrentUser } = useOutletContext<AppOutletContext>();
  usePageBreadcrumbs(passwordBreadcrumbFallback, currentUser.mustChangePassword);
  const navigate = useNavigate();
  const [draft, dispatch] = useReducer(passwordDraftReducer, emptyPasswordDraft);
  const [state, setState] = useState<MutationState>(idleMutationState);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const mismatch = passwordConfirmationError(draft);
    if (mismatch) { setState({ pending: false, error: mismatch }); return; }
    setState({ pending: true });
    try {
      await changeCurrentUserPassword(draft);
      dispatch({ type: "reset" });
      await refreshCurrentUser();
      setState({ pending: false, message: "Password changed." });
      if (currentUser.mustChangePassword) navigate("/profile", { replace: true });
    } catch (error: unknown) {
      setState({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    dispatch({ type: "reset" });
    setState(idleMutationState);
    navigate("/profile");
  }

  return <PasswordChangePageRegion
    draft={draft}
    state={state}
    mustChangePassword={currentUser.mustChangePassword}
    onSubmit={submit}
    onChange={(field, value) => dispatch({ type: "change", field, value })}
    onCancel={cancel}
  />;
}
