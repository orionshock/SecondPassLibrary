export function confirmDangerousAction(
  message: string,
  confirmAction: (message: string) => boolean = window.confirm,
): boolean {
  return confirmAction(message);
}
