import {
  ApiError,
  changeCurrentUserPassword,
  updateCurrentUser,
  type ChangeCurrentUserPasswordInput,
  type CurrentUser,
  type UpdateCurrentUserInput,
} from "@second-pass/spl-api";
import { useReducer, useState, type FormEvent } from "react";
import { useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { MaterialIcon } from "../../components/icons/MaterialIcon";
import {
  Badge,
  Button,
  ErrorPanel,
  FormField,
  KeyValueList,
  PageHeader,
  Surface,
} from "../../components/ui";
import { displayUserRole } from "../../domain/users/presentation";

interface MutationState {
  pending: boolean;
  message?: string;
  error?: ApiError | Error;
}

export interface ProfileDraft {
  email: string;
  firstName: string;
  lastName: string;
}

export interface PasswordDraft {
  currentPassword: string;
  newPassword: string;
  confirmPassword: string;
}

type ProfileDraftAction =
  | { type: "change"; field: keyof ProfileDraft; value: string }
  | { type: "reset"; value: ProfileDraft };

type PasswordDraftAction =
  | { type: "change"; field: keyof PasswordDraft; value: string }
  | { type: "reset" };

const idleMutation: MutationState = { pending: false };
const emptyPasswordDraft: PasswordDraft = {
  currentPassword: "",
  newPassword: "",
  confirmPassword: "",
};

export function ProfilePage() {
  const { currentUser, onCurrentUserChange } = useOutletContext<AppOutletContext>();
  const [profileState, setProfileState] = useState<MutationState>(idleMutation);
  const [passwordState, setPasswordState] = useState<MutationState>(idleMutation);

  async function saveProfile(input: UpdateCurrentUserInput) {
    setProfileState({ pending: true });
    try {
      const updated = await updateCurrentUser(input);
      onCurrentUserChange(updated);
      setProfileState({ pending: false, message: "Profile saved." });
    } catch (error: unknown) {
      setProfileState({ pending: false, error: normalizedError(error) });
    }
  }

  async function savePassword(input: ChangeCurrentUserPasswordInput) {
    setPasswordState({ pending: true });
    try {
      await changeCurrentUserPassword(input);
      onCurrentUserChange({ ...currentUser, mustChangePassword: false });
      setPasswordState({ pending: false, message: "Password changed." });
    } catch (error: unknown) {
      setPasswordState({ pending: false, error: normalizedError(error) });
    }
  }

  return (
    <ProfilePageView
      user={currentUser}
      profileState={profileState}
      passwordState={passwordState}
      onSaveProfile={saveProfile}
      onSavePassword={savePassword}
      onCancelProfile={() => setProfileState(idleMutation)}
      onCancelPassword={() => setPasswordState(idleMutation)}
    />
  );
}

export function ProfilePageView({
  user,
  profileState,
  passwordState,
  onSaveProfile,
  onSavePassword,
  onCancelProfile,
  onCancelPassword,
}: {
  user: CurrentUser;
  profileState: MutationState;
  passwordState: MutationState;
  onSaveProfile: (input: UpdateCurrentUserInput) => void | Promise<void>;
  onSavePassword: (input: ChangeCurrentUserPasswordInput) => void | Promise<void>;
  onCancelProfile: () => void;
  onCancelPassword: () => void;
}) {
  return (
    <div className="page-stack profile-page">
      <PageHeader eyebrow="Account" title="Profile" />
      <ProfileIdentityRegion user={user} />
      <ProfileDetailsRegion
        user={user}
        state={profileState}
        onSave={onSaveProfile}
        onCancel={onCancelProfile}
      />
      <PasswordRegion
        user={user}
        state={passwordState}
        onSave={onSavePassword}
        onCancel={onCancelPassword}
      />
    </div>
  );
}

function ProfileIdentityRegion({ user }: { user: CurrentUser }) {
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || "Not provided";
  return (
    <Surface title="Account identity">
      <KeyValueList items={[
        { label: "Username", value: user.username },
        { label: "Display name", value: displayName },
        { label: "Role", value: <Badge tone={user.isOwner ? "accent" : "default"}>{displayUserRole(user)}</Badge> },
        { label: "Email", value: user.email || "Not provided" },
      ]} />
    </Surface>
  );
}

function ProfileDetailsRegion({
  user,
  state,
  onSave,
  onCancel,
}: {
  user: CurrentUser;
  state: MutationState;
  onSave: (input: UpdateCurrentUserInput) => void | Promise<void>;
  onCancel: () => void;
}) {
  const [draft, dispatch] = useReducer(profileDraftReducer, user, profileDraftFromUser);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSave(draft);
  }

  function cancel() {
    dispatch({ type: "reset", value: profileDraftFromUser(user) });
    onCancel();
  }

  return (
    <Surface title="Profile details">
      <form className="form-grid" onSubmit={submit}>
        <FormField label="Email" htmlFor="profile-email" error={fieldError(state.error, "email")}>
          <input
            id="profile-email"
            name="email"
            type="email"
            value={draft.email}
            autoComplete="email"
            onChange={(event) => dispatch({ type: "change", field: "email", value: event.target.value })}
          />
        </FormField>
        <FormField label="First name" htmlFor="profile-first-name" error={fieldError(state.error, "first_name")}>
          <input
            id="profile-first-name"
            name="firstName"
            value={draft.firstName}
            autoComplete="given-name"
            onChange={(event) => dispatch({ type: "change", field: "firstName", value: event.target.value })}
          />
        </FormField>
        <FormField label="Last name" htmlFor="profile-last-name" error={fieldError(state.error, "last_name")}>
          <input
            id="profile-last-name"
            name="lastName"
            value={draft.lastName}
            autoComplete="family-name"
            onChange={(event) => dispatch({ type: "change", field: "lastName", value: event.target.value })}
          />
        </FormField>
        <ActionRow
          state={state}
          submitLabel="Save profile"
          pendingLabel="Saving..."
          onCancel={cancel}
        />
      </form>
    </Surface>
  );
}

function PasswordRegion({
  user,
  state,
  onSave,
  onCancel,
}: {
  user: CurrentUser;
  state: MutationState;
  onSave: (input: ChangeCurrentUserPasswordInput) => void | Promise<void>;
  onCancel: () => void;
}) {
  const [draft, dispatch] = useReducer(passwordDraftReducer, emptyPasswordDraft);

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void onSave(draft);
  }

  function cancel() {
    dispatch({ type: "reset" });
    onCancel();
  }

  return (
    <Surface title="Change password">
      {user.mustChangePassword ? <p className="section-note"><Badge tone="accent">Password change required</Badge></p> : null}
      <form className="form-grid" onSubmit={submit}>
        <FormField label="Current password" htmlFor="current-password" error={fieldError(state.error, "current_password")}>
          <input
            id="current-password"
            name="currentPassword"
            type="password"
            value={draft.currentPassword}
            autoComplete="current-password"
            required
            onChange={(event) => dispatch({ type: "change", field: "currentPassword", value: event.target.value })}
          />
        </FormField>
        <FormField label="New password" htmlFor="new-password" error={fieldError(state.error, "new_password")}>
          <input
            id="new-password"
            name="newPassword"
            type="password"
            value={draft.newPassword}
            autoComplete="new-password"
            required
            onChange={(event) => dispatch({ type: "change", field: "newPassword", value: event.target.value })}
          />
        </FormField>
        <FormField label="Confirm password" htmlFor="confirm-password" error={fieldError(state.error, "confirm_password")}>
          <input
            id="confirm-password"
            name="confirmPassword"
            type="password"
            value={draft.confirmPassword}
            autoComplete="new-password"
            required
            onChange={(event) => dispatch({ type: "change", field: "confirmPassword", value: event.target.value })}
          />
        </FormField>
        <ActionRow
          state={state}
          submitLabel="Change password"
          pendingLabel="Changing..."
          onCancel={cancel}
        />
      </form>
    </Surface>
  );
}

function ActionRow({
  state,
  submitLabel,
  pendingLabel,
  onCancel,
}: {
  state: MutationState;
  submitLabel: string;
  pendingLabel: string;
  onCancel: () => void;
}) {
  return (
    <div className="form-action-row">
      <div className={`action-feedback${state.error ? " action-feedback--error" : state.message ? " action-feedback--success" : ""}`}>
        {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
        {state.message ? (
          <span className="success-message" role="status">
            <MaterialIcon name="check_circle" className="success-icon" />
            {state.message}
          </span>
        ) : null}
      </div>
      <div className="form-actions">
        <Button type="button" className="button--secondary" disabled={state.pending} onClick={onCancel}>Cancel</Button>
        <Button type="submit" disabled={state.pending}>{state.pending ? pendingLabel : submitLabel}</Button>
      </div>
    </div>
  );
}

export function profileDraftFromUser(user: CurrentUser): ProfileDraft {
  return { email: user.email, firstName: user.firstName, lastName: user.lastName };
}

export function profileDraftReducer(state: ProfileDraft, action: ProfileDraftAction): ProfileDraft {
  if (action.type === "reset") return action.value;
  return { ...state, [action.field]: action.value };
}

export function passwordDraftReducer(state: PasswordDraft, action: PasswordDraftAction): PasswordDraft {
  if (action.type === "reset") return emptyPasswordDraft;
  return { ...state, [action.field]: action.value };
}

function normalizedError(error: unknown): ApiError | Error {
  return error instanceof Error ? error : new Error("The request could not be completed.");
}

function fieldError(error: ApiError | Error | undefined, field: string): string | undefined {
  return error instanceof ApiError ? error.fields?.[field]?.[0] : undefined;
}

export type { MutationState };
