import type { CreateUserRole, ManagedUser, ManagedUserRole } from "@second-pass/spl-api";

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

export function editableUserRoles(operator: UserRoleIdentity, target: ManagedUser): readonly ManagedUserRole[] {
  if (target.isOwner) return [];
  if (operator.isOwner) return ownerRoles;
  if (operator.role !== "manager" || target.role === "manager") return [];
  return managerRoles;
}
