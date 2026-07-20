import { ApiError, changeCurrentUserPassword, type ChangeCurrentUserPasswordInput } from "@second-pass/spl-api";
import { useReducer, useState, type Dispatch, type FormEvent } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { Button, FormField, PageHeader } from "../../components/ui";
import { fieldError, InlineFeedback, normalizedError, type MutationState } from "../profile/ProfilePage";

export type PasswordDraft = ChangeCurrentUserPasswordInput;
type PasswordAction = { type: "change"; field: keyof PasswordDraft; value: string } | { type: "reset" };
export const emptyPasswordDraft: PasswordDraft = { currentPassword: "", newPassword: "", confirmPassword: "" };

export function PasswordChangePage() {
  const { currentUser, refreshCurrentUser } = useOutletContext<AppOutletContext>();
  const navigate = useNavigate();
  const [draft, dispatch] = useReducer(passwordDraftReducer, emptyPasswordDraft);
  const [state, setState] = useState<MutationState>({ pending: false });

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
    } catch (error: unknown) { setState({ pending: false, error: normalizedError(error) }); }
  }

  function cancel() { dispatch({ type: "reset" }); setState({ pending: false }); navigate("/profile"); }
  return <div className="page-stack profile-page">
    {!currentUser.mustChangePassword ? <nav className="breadcrumbs" aria-label="Breadcrumb"><Link to="/profile">Profile</Link><span aria-hidden="true">/</span><span>Password</span></nav> : null}
    <PageHeader title="Change password" />
    {currentUser.mustChangePassword ? <p className="required-notice">You must change your password before continuing.</p> : null}
    <form className="form-grid" onSubmit={submit}>
      <PasswordField id="current-password" label="Current password" field="currentPassword" value={draft.currentPassword} state={state} dispatch={dispatch} autoComplete="current-password" />
      <PasswordField id="new-password" label="New password" field="newPassword" value={draft.newPassword} state={state} dispatch={dispatch} autoComplete="new-password" />
      <PasswordField id="confirm-password" label="Confirm password" field="confirmPassword" value={draft.confirmPassword} state={state} dispatch={dispatch} autoComplete="new-password" />
      <div className="form-action-row"><InlineFeedback state={state} /><div className="form-actions">{passwordCancelVisible(currentUser.mustChangePassword) ? <Button type="button" className="button--secondary" disabled={state.pending} onClick={cancel}>Cancel</Button> : null}<Button type="submit" disabled={state.pending}>{state.pending ? "Changing..." : "Change password"}</Button></div></div>
    </form>
  </div>;
}

function PasswordField({ id, label, field, value, state, dispatch, autoComplete }: { id: string; label: string; field: keyof PasswordDraft; value: string; state: MutationState; dispatch: Dispatch<PasswordAction>; autoComplete: string }) {
  const wireField = field === "currentPassword" ? "current_password" : field === "newPassword" ? "new_password" : "confirm_password";
  return <FormField label={label} htmlFor={id} error={fieldError(state.error, wireField)}><input id={id} type="password" required value={value} autoComplete={autoComplete} onChange={(event) => dispatch({ type: "change", field, value: event.target.value })} /></FormField>;
}

export function passwordDraftReducer(state: PasswordDraft, action: PasswordAction): PasswordDraft { return action.type === "reset" ? emptyPasswordDraft : { ...state, [action.field]: action.value }; }
export function passwordConfirmationError(draft: PasswordDraft): ApiError | undefined { return draft.newPassword === draft.confirmPassword ? undefined : new ApiError("Passwords do not match.", 400, { fields: { confirm_password: ["Passwords do not match."] } }); }
export function passwordCancelVisible(mustChangePassword: boolean): boolean { return !mustChangePassword; }
