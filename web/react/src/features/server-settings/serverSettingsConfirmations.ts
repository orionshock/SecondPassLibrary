import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";

export function confirmEnableAdvancedGroups(confirmAction?: (message: string) => boolean): boolean {
  return confirmDangerousAction(
    "Enable advanced library groups? This exposes separate group management. Turning it off later requires the Django Admin Service Hatch recovery flow.",
    confirmAction,
  );
}
