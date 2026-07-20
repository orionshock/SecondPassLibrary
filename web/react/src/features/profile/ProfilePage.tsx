import {
  ApiError,
  listClientSessions,
  logoutOtherWebSessions,
  revokeClientSession,
  updateCurrentUser,
  type ClientSession,
  type CurrentUser,
  type UpdateCurrentUserInput,
} from "@second-pass/spl-api";
import { useEffect, useReducer, useState, type FormEvent } from "react";
import { Link, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { Badge, Button, ErrorPanel, FormField, KeyValueList, PageHeader, Surface } from "../../components/ui";
import { displayUserRole } from "../../domain/users/presentation";

export interface MutationState { pending: boolean; message?: string; error?: ApiError | Error }
export interface ProfileDraft { email: string; firstName: string; lastName: string }
type ProfileDraftAction = { type: "change"; field: keyof ProfileDraft; value: string } | { type: "reset"; value: ProfileDraft };
const idleMutation: MutationState = { pending: false };

export function ProfilePage() {
  const { currentUser, onCurrentUserChange } = useOutletContext<AppOutletContext>();
  const [profileState, setProfileState] = useState<MutationState>(idleMutation);

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

  return <ProfilePageView user={currentUser} profileState={profileState} onSaveProfile={saveProfile} onCancelProfile={() => setProfileState(idleMutation)} />;
}

export function ProfilePageView({ user, profileState, onSaveProfile, onCancelProfile }: {
  user: CurrentUser;
  profileState: MutationState;
  onSaveProfile: (input: UpdateCurrentUserInput) => void | Promise<void>;
  onCancelProfile: () => void;
}) {
  return (
    <div className="page-stack profile-page">
      <PageHeader eyebrow="Account" title="Profile" />
      <ProfileIdentityRegion user={user} />
      <ProfileDetailsRegion user={user} state={profileState} onSave={onSaveProfile} onCancel={onCancelProfile} />
      <GroupMembershipRegion user={user} />
      <AccountSecurityRegion />
      <ConnectedClientsRegion />
    </div>
  );
}

function ProfileIdentityRegion({ user }: { user: CurrentUser }) {
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || "Not provided";
  return <Surface title="Account identity"><KeyValueList items={[
    { label: "Username", value: user.username },
    { label: "Display name", value: displayName },
    { label: "Role", value: <Badge tone={user.isOwner ? "accent" : "default"}>{displayUserRole(user)}</Badge> },
    { label: "Email", value: user.email || "Not provided" },
  ]} /></Surface>;
}

function ProfileDetailsRegion({ user, state, onSave, onCancel }: {
  user: CurrentUser; state: MutationState;
  onSave: (input: UpdateCurrentUserInput) => void | Promise<void>; onCancel: () => void;
}) {
  const [draft, dispatch] = useReducer(profileDraftReducer, user, profileDraftFromUser);
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void onSave(draft); }
  function cancel() { dispatch({ type: "reset", value: profileDraftFromUser(user) }); onCancel(); }
  return <Surface title="Profile details"><form className="form-grid" onSubmit={submit}>
    <FormField label="Email" htmlFor="profile-email" error={fieldError(state.error, "email")}><input id="profile-email" type="email" value={draft.email} autoComplete="email" onChange={(event) => dispatch({ type: "change", field: "email", value: event.target.value })} /></FormField>
    <FormField label="First name" htmlFor="profile-first-name" error={fieldError(state.error, "first_name")}><input id="profile-first-name" value={draft.firstName} autoComplete="given-name" onChange={(event) => dispatch({ type: "change", field: "firstName", value: event.target.value })} /></FormField>
    <FormField label="Last name" htmlFor="profile-last-name" error={fieldError(state.error, "last_name")}><input id="profile-last-name" value={draft.lastName} autoComplete="family-name" onChange={(event) => dispatch({ type: "change", field: "lastName", value: event.target.value })} /></FormField>
    <ActionRow state={state} submitLabel="Save profile" pendingLabel="Saving..." onCancel={cancel} />
  </form></Surface>;
}

function GroupMembershipRegion({ user }: { user: CurrentUser }) {
  if (!user.advancedLibraryGroupsEnabled) return null;
  return <Surface title="Group memberships"><div className="item-list">
    {user.groups.map((group) => <div className="item-row" key={group.id}><span>{group.name}</span><span className="item-badges">{group.isPublicGroup ? <Badge>Public</Badge> : null}{group.isCurator ? <Badge tone="accent">Curator</Badge> : <Badge>Member</Badge>}</span></div>)}
    {user.groups.length === 0 ? <p className="muted">No group memberships.</p> : null}
  </div></Surface>;
}

function AccountSecurityRegion() {
  const [state, setState] = useState<MutationState>(idleMutation);
  async function logoutOthers() {
    setState({ pending: true });
    try { await logoutOtherWebSessions(); setState({ pending: false, message: "Other web sessions logged out." }); }
    catch (error: unknown) { setState({ pending: false, error: normalizedError(error) }); }
  }
  return <Surface title="Account security"><div className="region-stack">
    <div className="item-row"><div><strong>Password</strong><p className="muted">Change the password for this account.</p></div><Link className="button" to="/password-change">Change password</Link></div>
    <div className="item-row"><div><strong>Web sessions</strong><p className="muted">Keep this browser signed in and end your other web sessions.</p></div><Button disabled={state.pending} onClick={() => void logoutOthers()}>{state.pending ? "Logging out..." : "Log out other sessions"}</Button></div>
    <InlineFeedback state={state} />
  </div></Surface>;
}

function ConnectedClientsRegion() {
  const [sessions, setSessions] = useState<ClientSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [state, setState] = useState<MutationState>(idleMutation);
  useEffect(() => { let active = true; listClientSessions().then((value) => { if (active) setSessions(value); }).catch((error) => { if (active) setState({ pending: false, error: normalizedError(error) }); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  async function revoke(session: ClientSession) {
    setState({ pending: true });
    try { await revokeClientSession(session.id); setSessions((current) => current.filter(({ id }) => id !== session.id)); setState({ pending: false, message: `${session.name} revoked.` }); }
    catch (error: unknown) { setState({ pending: false, error: normalizedError(error) }); }
  }
  return <Surface title="Connected clients"><div className="region-stack">
    <div className="section-actions"><p className="muted">Reader clients paired with this account.</p><Link className="button" to="/profile/client-pairing">Pair a client</Link></div>
    {loading ? <p aria-live="polite">Loading connected clients...</p> : null}
    {!loading && sessions.length === 0 ? <p className="muted">No connected clients.</p> : null}
    {sessions.map((session) => <div className="item-row" key={session.id}><div><strong>{session.name}</strong><p className="muted">{session.clientType}{session.lastSeenAt ? ` · Last seen ${new Date(session.lastSeenAt).toLocaleString()}` : ""}</p></div><Button className="button--secondary" disabled={state.pending} onClick={() => void revoke(session)}>Revoke</Button></div>)}
    <InlineFeedback state={state} />
  </div></Surface>;
}

function ActionRow({ state, submitLabel, pendingLabel, onCancel }: { state: MutationState; submitLabel: string; pendingLabel: string; onCancel: () => void }) {
  return <div className="form-action-row"><InlineFeedback state={state} /><div className="form-actions"><Button type="button" className="button--secondary" disabled={state.pending} onClick={onCancel}>Cancel</Button><Button type="submit" disabled={state.pending}>{state.pending ? pendingLabel : submitLabel}</Button></div></div>;
}

export function InlineFeedback({ state }: { state: MutationState }) {
  return <div className={`action-feedback${state.error ? " action-feedback--error" : state.message ? " action-feedback--success" : ""}`}>{state.error ? <ErrorPanel>{state.error.message}</ErrorPanel> : null}{state.message ? <span className="success-message" role="status"><MaterialIcon name="check_circle" className="success-icon" />{state.message}</span> : null}</div>;
}

export function profileDraftFromUser(user: CurrentUser): ProfileDraft { return { email: user.email, firstName: user.firstName, lastName: user.lastName }; }
export function profileDraftReducer(state: ProfileDraft, action: ProfileDraftAction): ProfileDraft { return action.type === "reset" ? action.value : { ...state, [action.field]: action.value }; }
export function normalizedError(error: unknown): ApiError | Error { return error instanceof Error ? error : new Error("The request could not be completed."); }
export function fieldError(error: ApiError | Error | undefined, field: string): string | undefined { return error instanceof ApiError ? error.fields?.[field]?.[0] : undefined; }
