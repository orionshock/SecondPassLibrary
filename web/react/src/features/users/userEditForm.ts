import type { ManagedUser, ManagedUserRole, UpdateManagedUserInput } from "@second-pass/spl-api";

export interface UserEditDraft {
  email: string;
  firstName: string;
  lastName: string;
  role: ManagedUserRole;
  isActive: boolean;
}

export type UserEditDraftAction =
  | { type: "change"; field: "email" | "firstName" | "lastName" | "role"; value: string }
  | { type: "active"; value: boolean }
  | { type: "reset"; value: UserEditDraft };

export function userEditDraftFromUser(user: ManagedUser): UserEditDraft {
  return {
    email: user.email,
    firstName: user.firstName,
    lastName: user.lastName,
    role: user.role as ManagedUserRole,
    isActive: user.isActive,
  };
}

export function userEditDraftReducer(state: UserEditDraft, action: UserEditDraftAction): UserEditDraft {
  if (action.type === "reset") return action.value;
  if (action.type === "active") return { ...state, isActive: action.value };
  return { ...state, [action.field]: action.value };
}

export function userEditInputFromDraft(draft: UserEditDraft, canChangeRole: boolean, canChangeActive: boolean): UpdateManagedUserInput {
  return {
    email: draft.email,
    firstName: draft.firstName,
    lastName: draft.lastName,
    ...(canChangeRole ? { role: draft.role } : {}),
    ...(canChangeActive ? { isActive: draft.isActive } : {}),
  };
}
