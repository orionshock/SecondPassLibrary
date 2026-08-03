export function confirmGroupBookRemoval(
  confirm: (message: string) => boolean = window.confirm,
): boolean {
  return confirm(
    "Remove this book from the group? It will also be removed from shelves owned by this group.",
  );
}

export function confirmGroupMemberRemoval(
  confirm: (message: string) => boolean = window.confirm,
): boolean {
  return confirm("Remove this member from the group?");
}
