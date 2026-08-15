import { confirmDangerousAction } from "../../../shared/confirmations/confirmDangerousAction";

export function confirmManagedPasswordReset(confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction("Reset this user's password and revoke their active sessions?", confirmAction);
}

export function confirmGroupMembershipRemoval(groupName: string, confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction(`Remove this user from ${groupName}?`, confirmAction);
}
