import type { ClientSession } from "@second-pass/spl-api";
import { Link } from "react-router";

import type { BreadcrumbLocationState } from "../../../app/navigation/breadcrumbs";
import { Button, Surface } from "../../../components/UiPrimitives";
import { ActionFeedback } from "../../../shared/feedback/ActionFeedback";
import type { MutationState } from "../../../shared/feedback/mutationState";
import { ClientSessionRow } from "../components/ClientSessionRow";

export function AccountSessionsPageRegion({ sessions, loading, clientState, webState, clientPairingLinkState, onLogoutOthers, onRevokeSession }: {
  sessions: ClientSession[];
  loading: boolean;
  clientState: MutationState;
  webState: MutationState;
  clientPairingLinkState: BreadcrumbLocationState;
  onLogoutOthers: () => void | Promise<void>;
  onRevokeSession: (session: ClientSession) => void | Promise<void>;
}) {
  return <Surface><div className="region-stack">
    <div className="session-management-row"><span className="profile-row-label">Session management</span><div className="session-management-controls"><ActionFeedback state={webState} /><Button disabled={webState.pending} onClick={() => void onLogoutOthers()}>{webState.pending ? "Logging out..." : "Log Out All Other Web Sessions"}</Button></div></div>
    <div className="section-divider" />
    <div className="section-actions"><h2 className="surface-title">Device/API sessions</h2><Link className="button" to="/profile/client-pairing" state={clientPairingLinkState}>Connect a Device/App</Link></div>
    {loading ? <p aria-live="polite">Loading connected clients...</p> : null}
    {!loading && sessions.length === 0 ? <p className="muted">No connected clients.</p> : null}
    {sessions.length > 0 ? <div className="session-table-wrap"><table className="session-table"><thead><tr><th aria-label="Actions" /><th>Device/client name</th><th>Type</th><th>Last seen</th></tr></thead><tbody>{sessions.map((session) => <ClientSessionRow key={session.id} session={session} disabled={clientState.pending} onRevoke={(value) => void onRevokeSession(value)} />)}</tbody></table></div> : null}
    <ActionFeedback state={clientState} />
  </div></Surface>;
}
