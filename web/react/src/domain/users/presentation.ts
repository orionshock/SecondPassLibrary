export interface UserRoleIdentity {
  role: string;
  isOwner: boolean;
}

const roleLabels: Record<string, string> = {
  owner: "Owner",
  manager: "Manager",
  librarian: "Librarian",
  curator: "Curator",
  reader: "Reader",
};

export function displayUserRole(user: UserRoleIdentity): string {
  if (user.isOwner) return "Owner";
  return displayUserRoleName(user.role);
}

export function displayUserRoleName(role: string): string {
  return roleLabels[role] ?? titleCase(role || "reader");
}

function titleCase(value: string): string {
  return `${value[0].toUpperCase()}${value.slice(1).toLowerCase()}`;
}
