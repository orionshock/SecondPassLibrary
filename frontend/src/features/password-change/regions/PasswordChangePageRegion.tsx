import type { FormEvent } from "react";

import { Button, FormField } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRow } from "../../../shared/forms/ActionRow";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { passwordCancelVisible, type PasswordDraft } from "../passwordChangeForm";

export function PasswordChangePageRegion({ draft, state, mustChangePassword, onSubmit, onChange, onCancel }: {
  draft: PasswordDraft;
  state: MutationState;
  mustChangePassword: boolean;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  onChange: (field: keyof PasswordDraft, value: string) => void;
  onCancel: () => void;
}) {
  return <ProductPageShell className="account-page" title="Change password">
    {mustChangePassword ? <p className="required-notice">You must change your password before continuing.</p> : null}
    <form className="form-grid" onSubmit={onSubmit}>
      <PasswordField id="current-password" label="Current password" field="currentPassword" value={draft.currentPassword} state={state} onChange={onChange} autoComplete="current-password" />
      <PasswordField id="new-password" label="New password" field="newPassword" value={draft.newPassword} state={state} onChange={onChange} autoComplete="new-password" />
      <PasswordField id="confirm-password" label="Confirm password" field="confirmPassword" value={draft.confirmPassword} state={state} onChange={onChange} autoComplete="new-password" />
      <ActionRow state={state}>
        {passwordCancelVisible(mustChangePassword) ? <Button type="button" tone="secondary" disabled={state.pending} onClick={onCancel}>Cancel</Button> : null}
        <Button type="submit" disabled={state.pending}>{state.pending ? "Changing..." : "Change password"}</Button>
      </ActionRow>
    </form>
  </ProductPageShell>;
}

function PasswordField({ id, label, field, value, state, onChange, autoComplete }: {
  id: string;
  label: string;
  field: keyof PasswordDraft;
  value: string;
  state: MutationState;
  onChange: (field: keyof PasswordDraft, value: string) => void;
  autoComplete: string;
}) {
  return <FormField label={label} htmlFor={id} error={fieldError(state.error, field)}><input id={id} type="password" required value={value} autoComplete={autoComplete} onChange={(event) => onChange(field, event.target.value)} /></FormField>;
}
