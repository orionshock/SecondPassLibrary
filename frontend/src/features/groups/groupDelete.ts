import { confirmDangerousAction } from "../../shared/confirmations/confirmDangerousAction";

export function confirmGroupDelete(
  confirm: (message: string) => boolean = window.confirm,
): boolean {
  return confirmDangerousAction(
    "Delete this group? This removes its memberships and book assignments, deletes shelves owned by this group, and restores otherwise unassigned users and books to Public/Common Room. Users, books, EPUB files, and covers are not deleted.",
    confirm,
  );
}
