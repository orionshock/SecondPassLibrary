import type { ClientSession } from "@second-pass/spl-api";

import { RemoveIconButton } from "../../../components/icons/RemoveIconButton";

export function ClientSessionRow({ session, disabled, onRevoke }: {
  session: ClientSession;
  disabled: boolean;
  onRevoke: (session: ClientSession) => void;
}) {
  return <tr><td><RemoveIconButton label={`Revoke ${session.name}`} disabled={disabled} onClick={() => onRevoke(session)} /></td><td>{session.name}</td><td>{session.clientType}</td><td>{session.lastSeenAt ? new Date(session.lastSeenAt).toLocaleString() : "Never"}</td></tr>;
}
