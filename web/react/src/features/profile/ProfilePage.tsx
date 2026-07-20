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
import { RemoveIconButton } from "../../components/icons/RemoveIconButton";
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
      <PageHeader eyebrow="Profile" title="Profile" actions={<Link className="button" to="/profile/password">Change password</Link>} />
      <ProfileDetailsRegion user={user} state={profileState} onSave={onSaveProfile} onCancel={onCancelProfile} />
      <GroupMembershipRegion user={user} />
      <AccountSessionsRegion />
    </div>
  );
}

function ProfileDetailsRegion({ user, state, onSave, onCancel }: {
  user: CurrentUser; state: MutationState;
  onSave: (input: UpdateCurrentUserInput) => void | Promise<void>; onCancel: () => void;
}) {
  const [draft, dispatch] = useReducer(profileDraftReducer, user, profileDraftFromUser);
  const [editing, setEditing] = useState(Boolean(state.error));
  useEffect(() => { if (state.message) setEditing(false); }, [state.message]);
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); void onSave(draft); }
  function edit() { onCancel(); setEditing(true); }
  function cancel() { dispatch({ type: "reset", value: profileDraftFromUser(user) }); onCancel(); setEditing(false); }
  const displayName = [user.firstName, user.lastName].filter(Boolean).join(" ") || user.username;
  return <Surface>
    <div className="profile-user-row">
      <span className="profile-row-label">User</span>
      <span className="profile-user-summary"><span>{displayName}</span><span className="css-dot" aria-hidden="true" /><span>&lt;@{user.username}&gt;</span><Badge tone={user.isOwner ? "accent" : "default"}>{displayUserRole(user)}</Badge></span>
      {!editing ? <div className="profile-edit-actions"><InlineFeedback state={state} /><Button type="button" onClick={edit}>Edit</Button></div> : null}
    </div>
    {editing ? <form className="form-grid profile-details-form" onSubmit={submit}>
      <FormField label="First Name" htmlFor="profile-first-name" error={fieldError(state.error, "first_name")}><input id="profile-first-name" value={draft.firstName} autoComplete="given-name" onChange={(event) => dispatch({ type: "change", field: "firstName", value: event.target.value })} /></FormField>
      <FormField label="Last Name" htmlFor="profile-last-name" error={fieldError(state.error, "last_name")}><input id="profile-last-name" value={draft.lastName} autoComplete="family-name" onChange={(event) => dispatch({ type: "change", field: "lastName", value: event.target.value })} /></FormField>
      <FormField label="Email" htmlFor="profile-email" error={fieldError(state.error, "email")}><input id="profile-email" type="email" value={draft.email} autoComplete="email" onChange={(event) => dispatch({ type: "change", field: "email", value: event.target.value })} /></FormField>
      <ActionRow state={state} submitLabel="Save profile" pendingLabel="Saving..." onCancel={cancel} />
    </form> : <KeyValueList items={[
      { label: "First Name", value: user.firstName || "Not provided" },
      { label: "Last Name", value: user.lastName || "Not provided" },
      { label: "Email", value: user.email || "Not provided" },
    ]} />}
  </Surface>;
}

function GroupMembershipRegion({ user }: { user: CurrentUser }) {
  if (!user.advancedLibraryGroupsEnabled) return null;
  return <Surface title="Group memberships"><div className="item-list">
    {user.groups.map((group) => <div className="item-row" key={group.id}><span>{group.name}</span><span className="item-badges">{group.isPublicGroup ? <Badge>Public</Badge> : null}{group.isCurator ? <Badge tone="accent">Curator</Badge> : <Badge>Member</Badge>}</span></div>)}
    {user.groups.length === 0 ? <p className="muted">No group memberships.</p> : null}
  </div></Surface>;
}

function AccountSessionsRegion() {
  const [sessions, setSessions] = useState<ClientSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [clientState, setClientState] = useState<MutationState>(idleMutation);
  const [webState, setWebState] = useState<MutationState>(idleMutation);
  useEffect(() => { let active = true; listClientSessions().then((value) => { if (active) setSessions(value); }).catch((error) => { if (active) setClientState({ pending: false, error: normalizedError(error) }); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, []);
  async function logoutOthers() {
    if (!confirmLogoutOtherWebSessions()) return;
    setWebState({ pending: true });
    try { await logoutOtherWebSessions(); setWebState({ pending: false, message: "Other web sessions logged out." }); }
    catch (error: unknown) { setWebState({ pending: false, error: normalizedError(error) }); }
  }
  async function revoke(session: ClientSession) {
    if (!confirmClientSessionRevoke(session.name)) return;
    setClientState({ pending: true });
    try { await revokeClientSession(session.id); setSessions((current) => current.filter(({ id }) => id !== session.id)); setClientState({ pending: false, message: `${session.name} revoked.` }); }
    catch (error: unknown) { setClientState({ pending: false, error: normalizedError(error) }); }
  }
  return <Surface><div className="region-stack">
    <div className="session-management-row"><span className="profile-row-label">Session management</span><div className="session-management-controls"><InlineFeedback state={webState} /><Button disabled={webState.pending} onClick={() => void logoutOthers()}>{webState.pending ? "Logging out..." : "Log Out All Other Web Sessions"}</Button></div></div>
    <div className="section-divider" />
    <div className="section-actions"><h2 className="surface-title">Device/API sessions</h2><Link className="button" to="/profile/client-pairing">Connect a Device/App</Link></div>
    {loading ? <p aria-live="polite">Loading connected clients...</p> : null}
    {!loading && sessions.length === 0 ? <p className="muted">No connected clients.</p> : null}
    {sessions.length > 0 ? <div className="session-table-wrap"><table className="session-table"><thead><tr><th aria-label="Actions" /><th>Device/client name</th><th>Type</th><th>Last seen</th></tr></thead><tbody>{sessions.map((session) => <tr key={session.id}><td><RemoveIconButton label={`Revoke ${session.name}`} disabled={clientState.pending} onClick={() => void revoke(session)} /></td><td>{session.name}</td><td>{session.clientType}</td><td>{session.lastSeenAt ? new Date(session.lastSeenAt).toLocaleString() : "Never"}</td></tr>)}</tbody></table></div> : null}
    <InlineFeedback state={clientState} />
  </div></Surface>;
}

export function confirmClientSessionRevoke(
  clientName: string,
  confirmAction: (message: string) => boolean = window.confirm,
): boolean {
  return confirmAction(`Revoke ${clientName}? This client will need to pair again.`);
}

export function confirmLogoutOtherWebSessions(
  confirmAction: (message: string) => boolean = window.confirm,
): boolean {
  return confirmAction("Log out all other web sessions? This browser will remain signed in.");
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
