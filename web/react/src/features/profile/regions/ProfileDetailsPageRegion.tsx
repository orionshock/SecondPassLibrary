import type { CurrentUser, UpdateCurrentUserInput } from "@second-pass/spl-api";
import { useEffect, useReducer, useState, type FormEvent } from "react";

import { Badge, Button, FormField, KeyValueList, Surface } from "../../../components/ui";
import { displayUserRole } from "../../../domain/users/presentation";
import { ActionFeedbackComponent } from "../../../shared/feedback/ActionFeedbackComponent";
import { fieldError, type MutationState } from "../../../shared/feedback/mutationState";
import { SaveCancelActionRowComponent } from "../../../shared/forms/ActionRowComponent";

export interface ProfileDraft { email: string; firstName: string; lastName: string }
type ProfileDraftAction = { type: "change"; field: keyof ProfileDraft; value: string } | { type: "reset"; value: ProfileDraft };

export function ProfileDetailsPageRegion({ user, state, onSave, onClearStatus }: {
  user: CurrentUser;
  state: MutationState;
  onSave: (input: UpdateCurrentUserInput) => void | Promise<void>;
  onClearStatus: () => void;
}) {
  const [draft, dispatch] = useReducer(profileDraftReducer, user, profileDraftFromUser);
  const [editing, setEditing] = useState(Boolean(state.error));
  useEffect(() => { if (state.message) setEditing(false); }, [state.message]);
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void onSave(draft); }
  function edit() { onClearStatus(); setEditing(true); }
  function cancel() { dispatch({ type: "reset", value: profileDraftFromUser(user) }); onClearStatus(); setEditing(false); }
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || user.username;

  return <Surface>
    <div className="profile-user-row">
      <span className="profile-row-label">User</span>
      <span className="profile-user-summary"><span>{displayName}</span><span className="css-dot" aria-hidden="true" /><span>&lt;@{user.username}&gt;</span><Badge tone={user.isOwner ? "accent" : "default"}>{displayUserRole(user)}</Badge></span>
      {!editing ? <div className="profile-edit-actions"><ActionFeedbackComponent state={state} /><Button type="button" onClick={edit}>Edit</Button></div> : null}
    </div>
    {editing ? <form className="form-grid profile-details-form" onSubmit={submit}>
      <FormField label="First Name" htmlFor="profile-first-name" error={fieldError(state.error, "firstName")}><input id="profile-first-name" value={draft.firstName} autoComplete="given-name" onChange={(event) => dispatch({ type: "change", field: "firstName", value: event.target.value })} /></FormField>
      <FormField label="Last Name" htmlFor="profile-last-name" error={fieldError(state.error, "lastName")}><input id="profile-last-name" value={draft.lastName} autoComplete="family-name" onChange={(event) => dispatch({ type: "change", field: "lastName", value: event.target.value })} /></FormField>
      <FormField label="Email" htmlFor="profile-email" error={fieldError(state.error, "email")}><input id="profile-email" type="email" value={draft.email} autoComplete="email" onChange={(event) => dispatch({ type: "change", field: "email", value: event.target.value })} /></FormField>
      <SaveCancelActionRowComponent state={state} submitLabel="Save profile" pendingLabel="Saving..." onCancel={cancel} />
    </form> : <KeyValueList items={[
      { label: "First Name", value: user.firstName || "Not provided" },
      { label: "Last Name", value: user.lastName || "Not provided" },
      { label: "Email", value: user.email || "Not provided" },
    ]} />}
  </Surface>;
}

export function profileDraftFromUser(user: CurrentUser): ProfileDraft { return { email: user.email, firstName: user.firstName, lastName: user.lastName }; }
export function profileDraftReducer(state: ProfileDraft, action: ProfileDraftAction): ProfileDraft { return action.type === "reset" ? action.value : { ...state, [action.field]: action.value }; }
