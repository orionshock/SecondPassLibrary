import type { ManagedUser, ManagedUserRole, UpdateManagedUserInput } from "@second-pass/spl-api";
import { useEffect, useReducer, type FormEvent } from "react";

import { FormField } from "../../../components/ui";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { SaveCancelActionRowComponent } from "../../../shared/forms/ActionRowComponent";
import { displayUserRole, displayUserRoleName } from "../../../domain/users/presentation";
import { userEditDraftFromUser, userEditDraftReducer, userEditInputFromDraft } from "../userEditForm";

export function UserDetailsPageRegion({ user, roles, canEdit, canChangeActive, state, onSave, onClearStatus }: {
  user: ManagedUser;
  roles: readonly ManagedUserRole[];
  canEdit: boolean;
  canChangeActive: boolean;
  state: MutationState;
  onSave: (input: UpdateManagedUserInput) => void | Promise<void>;
  onClearStatus: () => void;
}) {
  const [draft, dispatch] = useReducer(userEditDraftReducer, user, userEditDraftFromUser);
  useEffect(() => dispatch({ type: "reset", value: userEditDraftFromUser(user) }), [user]);
  const canChangeRole = roles.length > 0;
  function cancel() { dispatch({ type: "reset", value: userEditDraftFromUser(user) }); onClearStatus(); }
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSave(userEditInputFromDraft(draft, canChangeRole, canChangeActive));
  }

  return <section className="user-edit-region" aria-labelledby="user-details-heading">
    <h2 id="user-details-heading">User details</h2>
    {!canEdit ? <p className="muted">Use Profile to manage your own account.</p> : null}
    <form className="form-grid user-edit-form" onSubmit={submit}>
      <FormField label="First name" htmlFor="managed-user-first-name" error={fieldError(state.error, "first_name")}><input id="managed-user-first-name" disabled={!canEdit} value={draft.firstName} onChange={(event) => dispatch({ type: "change", field: "firstName", value: event.target.value })} /></FormField>
      <FormField label="Last name" htmlFor="managed-user-last-name" error={fieldError(state.error, "last_name")}><input id="managed-user-last-name" disabled={!canEdit} value={draft.lastName} onChange={(event) => dispatch({ type: "change", field: "lastName", value: event.target.value })} /></FormField>
      <FormField label="Email" htmlFor="managed-user-email" error={fieldError(state.error, "email")}><input id="managed-user-email" type="email" disabled={!canEdit} value={draft.email} onChange={(event) => dispatch({ type: "change", field: "email", value: event.target.value })} /></FormField>
      <FormField label="Role" htmlFor="managed-user-role" error={fieldError(state.error, "role")}>
        <select id="managed-user-role" disabled={!canChangeRole} value={canChangeRole ? draft.role : user.role} onChange={(event) => dispatch({ type: "change", field: "role", value: event.target.value })}>
          {canChangeRole ? roles.map((role) => <option key={role} value={role}>{displayUserRoleName(role)}</option>) : <option value={user.role}>{displayUserRole(user)}</option>}
        </select>
      </FormField>
      <FormField label="Active" htmlFor="managed-user-active" error={fieldError(state.error, "is_active")}>
        <select id="managed-user-active" disabled={!canChangeActive} value={draft.isActive ? "active" : "inactive"} onChange={(event) => dispatch({ type: "active", value: event.target.value === "active" })}>
          <option value="active">Active</option><option value="inactive">Inactive</option>
        </select>
      </FormField>
      {canEdit ? <SaveCancelActionRowComponent state={state} submitLabel="Save user" pendingLabel="Saving..." onCancel={cancel} /> : null}
    </form>
  </section>;
}
