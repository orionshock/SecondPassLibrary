import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";

export function confirmManagedPasswordReset(username: string, confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction(`Reset @${username}'s password and revoke their active sessions?`, confirmAction);
}

export function confirmGroupMembershipRemoval(groupName: string, confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction(`Remove this user from ${groupName}?`, confirmAction);
}
