import {
  ApiError,
  changeCurrentUserPassword,
  updateCurrentUser,
  type ChangeCurrentUserPasswordInput,
  type CurrentUser,
  type UpdateCurrentUserInput,
} from "@second-pass/spl-api";
import { useState, type FormEvent } from "react";
import { useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import {
  Badge,
  Button,
  ErrorPanel,
  FormField,
  KeyValueList,
  PageHeader,
  Surface,
} from "../../components/ui";

interface MutationState {
  pending: boolean;
  message?: string;
  error?: ApiError | Error;
}

const idleMutation: MutationState = { pending: false };

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
    />
  );
}

export function ProfilePageView({
  user,
  profileState,
  passwordState,
  onSaveProfile,
  onSavePassword,
}: {
  user: CurrentUser;
  profileState: MutationState;
  passwordState: MutationState;
  onSaveProfile: (input: UpdateCurrentUserInput) => void | Promise<void>;
  onSavePassword: (input: ChangeCurrentUserPasswordInput) => void | Promise<void>;
}) {
  return (
    <div className="page-stack">
      <PageHeader
        eyebrow="Account"
        title="Profile"
        description="Review your identity, update safe profile fields, or change your password."
      />
      <ProfileIdentityRegion user={user} />
      <ProfileDetailsRegion user={user} state={profileState} onSave={onSaveProfile} />
      <PasswordRegion user={user} state={passwordState} onSave={onSavePassword} />
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
        { label: "Role", value: <Badge>{titleCase(user.role)}</Badge> },
        { label: "Owner", value: user.isOwner ? <Badge tone="accent">Owner</Badge> : "No" },
        { label: "Email", value: user.email || "Not provided" },
      ]} />
    </Surface>
  );
}

function ProfileDetailsRegion({
  user,
  state,
  onSave,
}: {
  user: CurrentUser;
  state: MutationState;
  onSave: (input: UpdateCurrentUserInput) => void | Promise<void>;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void onSave({
      email: String(data.get("email") ?? "").trim(),
      firstName: String(data.get("firstName") ?? "").trim(),
      lastName: String(data.get("lastName") ?? "").trim(),
    });
  }

  return (
    <Surface title="Profile details">
      <form className="form-grid" onSubmit={submit}>
        {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
        <FormField label="Email" htmlFor="profile-email" error={fieldError(state.error, "email")}>
          <input id="profile-email" name="email" type="email" defaultValue={user.email} autoComplete="email" />
        </FormField>
        <FormField label="First name" htmlFor="profile-first-name" error={fieldError(state.error, "first_name")}>
          <input id="profile-first-name" name="firstName" defaultValue={user.firstName} autoComplete="given-name" />
        </FormField>
        <FormField label="Last name" htmlFor="profile-last-name" error={fieldError(state.error, "last_name")}>
          <input id="profile-last-name" name="lastName" defaultValue={user.lastName} autoComplete="family-name" />
        </FormField>
        <div className="form-actions">
          <Button type="submit" disabled={state.pending}>{state.pending ? "Saving…" : "Save profile"}</Button>
          {state.message ? <span className="success-message" role="status">{state.message}</span> : null}
        </div>
      </form>
    </Surface>
  );
}

function PasswordRegion({
  user,
  state,
  onSave,
}: {
  user: CurrentUser;
  state: MutationState;
  onSave: (input: ChangeCurrentUserPasswordInput) => void | Promise<void>;
}) {
  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    void Promise.resolve(onSave({
      currentPassword: String(data.get("currentPassword") ?? ""),
      newPassword: String(data.get("newPassword") ?? ""),
      confirmPassword: String(data.get("confirmPassword") ?? ""),
    }));
  }

  return (
    <Surface title="Change password">
      {user.mustChangePassword ? <p><Badge tone="accent">Password change required</Badge></p> : null}
      <form className="form-grid" onSubmit={submit}>
        {state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}
        <FormField label="Current password" htmlFor="current-password" error={fieldError(state.error, "current_password")}>
          <input id="current-password" name="currentPassword" type="password" autoComplete="current-password" required />
        </FormField>
        <FormField label="New password" htmlFor="new-password" error={fieldError(state.error, "new_password")}>
          <input id="new-password" name="newPassword" type="password" autoComplete="new-password" required />
        </FormField>
        <FormField label="Confirm new password" htmlFor="confirm-password" error={fieldError(state.error, "confirm_password")}>
          <input id="confirm-password" name="confirmPassword" type="password" autoComplete="new-password" required />
        </FormField>
        <div className="form-actions">
          <Button type="submit" disabled={state.pending}>{state.pending ? "Changing…" : "Change password"}</Button>
          {state.message ? <span className="success-message" role="status">{state.message}</span> : null}
        </div>
      </form>
    </Surface>
  );
}

function normalizedError(error: unknown): ApiError | Error {
  return error instanceof Error ? error : new Error("The request could not be completed.");
}

function fieldError(error: ApiError | Error | undefined, field: string): string | undefined {
  return error instanceof ApiError ? error.fields?.[field]?.[0] : undefined;
}

function titleCase(value: string): string {
  return value ? `${value[0].toUpperCase()}${value.slice(1).toLowerCase()}` : "Reader";
}

export type { MutationState };
