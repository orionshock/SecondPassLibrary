import type { ClientSession } from "@second-pass/spl-api";
import { Link } from "react-router";

import type { BreadcrumbLocationState } from "../../../app/navigation/breadcrumbs";
import { Button, Surface } from "../../../components/UiPrimitives";
import { ActionFeedback } from "../../../shared/feedback/ActionFeedback";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { ClientSessionRow } from "../components/ClientSessionRow";

export function AccountSessionsPageRegion({ sessions, loading, clientState, bulkClientState, webState, clientPairingLinkState, onLogoutOthers, onRevokeAllSessions, onRevokeSession }: {
  sessions: ClientSession[];
  loading: boolean;
  clientState: MutationState;
  bulkClientState: MutationState;
  webState: MutationState;
  clientPairingLinkState: BreadcrumbLocationState;
  onLogoutOthers: () => void | Promise<void>;
  onRevokeAllSessions: () => void | Promise<void>;
  onRevokeSession: (session: ClientSession) => void | Promise<void>;
}) {
  const clientMutationPending = clientState.pending || bulkClientState.pending;
  return <Surface><div className="region-stack">
    <div className="session-management-row"><span className="profile-row-label">Sessions</span><div className="session-management-controls"><div><ActionFeedback state={webState} /><ActionFeedback state={bulkClientState} /></div><div className="session-management-actions"><Button disabled={webState.pending} onClick={() => void onLogoutOthers()}>{webState.pending ? "Logging out…" : "Log out other web sessions"}</Button><Button disabled={loading || sessions.length === 0 || clientMutationPending} onClick={() => void onRevokeAllSessions()}>{bulkClientState.pending ? "Disconnecting…" : "Disconnect all devices and apps"}</Button></div></div></div>
    <div className="section-divider" />
    <div className="section-actions"><h2 className="surface-title">Device and API sessions</h2><Link className="button" to="/profile/client-pairing" state={clientPairingLinkState}>Connect a device or app</Link></div>
    {loading ? <p aria-live="polite">Loading connected clients...</p> : null}
    {!loading && sessions.length === 0 ? <p className="muted">No connected clients.</p> : null}
    {sessions.length > 0 ? <div className="session-table-wrap"><table className="session-table"><thead><tr><th scope="col">Actions</th><th scope="col">Device/client name</th><th scope="col">Type</th><th scope="col">Last seen</th></tr></thead><tbody>{sessions.map((session) => <ClientSessionRow key={session.id} session={session} disabled={clientMutationPending} onRevoke={(value) => void onRevokeSession(value)} />)}</tbody></table></div> : null}
    <ActionFeedback state={clientState} />
  </div></Surface>;
}
