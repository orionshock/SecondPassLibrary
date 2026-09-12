import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";

export function confirmEnableAdvancedGroups(confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction(
    "Enable Advanced Library Groups? Turning this off later requires a recovery action in Django Admin.",
    confirmAction,
  );
}
