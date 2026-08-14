import type { CreateUserRole } from "@second-pass/spl-api";
import type { FormEvent } from "react";
import { Link } from "react-router";

import { Button, FormField } from "../../../components/UiPrimitives";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { ActionRow } from "../../../shared/forms/ActionRow";
import type { UserCreateDraft, UserCreateDraftField } from "../userCreateForm";
import { createUserRoleLabel } from "../userCreateRoles";

export function UserCreateFormPageRegion({ draft, roles, state, onChange, onSubmit }: {
  draft: UserCreateDraft;
  roles: readonly CreateUserRole[];
  state: MutationState;
  onChange: (field: UserCreateDraftField, value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return <form className="form-grid user-create-form" onSubmit={onSubmit}>
    <FormField label="Username" htmlFor="user-create-username" error={fieldError(state.error, "username")}>
      <input id="user-create-username" required autoComplete="username" value={draft.username} onChange={(event) => onChange("username", event.target.value)} />
    </FormField>
    <FormField label="Email" htmlFor="user-create-email" error={fieldError(state.error, "email")}>
      <input id="user-create-email" type="email" autoComplete="email" value={draft.email} onChange={(event) => onChange("email", event.target.value)} />
    </FormField>
    <FormField label="First name" htmlFor="user-create-first-name" error={fieldError(state.error, "firstName")}>
      <input id="user-create-first-name" autoComplete="given-name" value={draft.firstName} onChange={(event) => onChange("firstName", event.target.value)} />
    </FormField>
    <FormField label="Last name" htmlFor="user-create-last-name" error={fieldError(state.error, "lastName")}>
      <input id="user-create-last-name" autoComplete="family-name" value={draft.lastName} onChange={(event) => onChange("lastName", event.target.value)} />
    </FormField>
    <FormField label="Role" htmlFor="user-create-role" error={fieldError(state.error, "role")}>
      <select id="user-create-role" value={draft.role} onChange={(event) => onChange("role", event.target.value)}>
        {roles.map((role) => <option key={role} value={role}>{createUserRoleLabel(role)}</option>)}
      </select>
    </FormField>
    <ActionRow state={state}>
      <Link className="button button--secondary" to="/users">Cancel</Link>
      <Button type="submit" disabled={state.pending}>{state.pending ? "Creating..." : "Create User"}</Button>
    </ActionRow>
  </form>;
}
