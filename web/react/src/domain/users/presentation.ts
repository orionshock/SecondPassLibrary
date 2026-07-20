export interface UserRoleIdentity {
  role: string;
  isOwner: boolean;
}

const roleLabels: Record<string, string> = {
  manager: "Manager",
  librarian: "Librarian",
  reader: "Reader",
};

export function displayUserRole(user: UserRoleIdentity): string {
  if (user.isOwner) return "Owner";
  return roleLabels[user.role] ?? titleCase(user.role || "reader");
}

function titleCase(value: string): string {
  return `${value[0].toUpperCase()}${value.slice(1).toLowerCase()}`;
}
