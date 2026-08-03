import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";

export function confirmClientSessionRevoke(
  clientName: string,
  confirmAction?: (message: string) => boolean,
): boolean {
  return confirmDangerousAction(`Revoke ${clientName}? This client will need to pair again.`, confirmAction);
}

export function confirmLogoutOtherWebSessions(confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction("Log out all other web sessions? This browser will remain signed in.", confirmAction);
}
