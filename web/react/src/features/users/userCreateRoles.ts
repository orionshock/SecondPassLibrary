import type { CreateUserRole } from "@second-pass/spl-api";

import { displayUserRoleName, type UserRoleIdentity } from "../../domain/users/presentation";

const ownerRoles: readonly CreateUserRole[] = ["manager", "librarian", "reader"];
const managerRoles: readonly CreateUserRole[] = ["librarian", "reader"];

export function creatableUserRoles(user: UserRoleIdentity): readonly CreateUserRole[] {
  if (user.isOwner) return ownerRoles;
  return user.role === "manager" ? managerRoles : [];
}

export function createUserRoleLabel(role: CreateUserRole): string {
  return displayUserRoleName(role);
}
