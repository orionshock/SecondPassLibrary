import type { ManagedPasswordResetResult } from "@second-pass/spl-api";

import { Button } from "../../../components/ui";
import { ActionFeedbackComponent } from "../../../shared/feedback/ActionFeedbackComponent";
import { ActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { TemporaryPasswordResultComponent } from "../../../shared/TemporaryPasswordResultComponent";

export function UserPasswordPageRegion({ mustChangePassword, canManage, requirementState, resetState, resetResult, onRequirementChange, onReset }: {
  mustChangePassword: boolean;
  canManage: boolean;
  requirementState: MutationState;
  resetState: MutationState;
  resetResult?: ManagedPasswordResetResult;
  onRequirementChange: (value: boolean) => void;
  onReset: () => void;
}) {
  return <section className="user-edit-region" aria-labelledby="managed-user-password-heading">
    <h2 id="managed-user-password-heading">Password</h2>
    <div className="user-password-requirement-row">
      <label><input type="checkbox" disabled={!canManage || requirementState.pending} checked={mustChangePassword} onChange={(event) => onRequirementChange(event.target.checked)} /> Require password change on next login</label>
      <ActionFeedbackComponent state={requirementState} />
    </div>
    <div className="user-password-reset">
      <div className="user-password-reset-row">
        <p className="muted">Generate a temporary password and revoke the user’s active sessions.</p>
        <ActionRowComponent state={resetState}><Button type="button" disabled={!canManage || resetState.pending} onClick={onReset}>{resetState.pending ? "Resetting..." : "Reset password"}</Button></ActionRowComponent>
      </div>
      {resetResult ? <div className="temporary-password-field"><label htmlFor="managed-user-temporary-password">Temporary credentials</label><TemporaryPasswordResultComponent id="managed-user-temporary-password" username={resetResult.username} password={resetResult.temporaryPassword} /></div> : null}
    </div>
  </section>;
}
