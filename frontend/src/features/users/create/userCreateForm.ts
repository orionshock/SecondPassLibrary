import type { CreateUserInput, CreateUserRole } from "@second-pass/spl-api";

export interface UserCreateDraft {
  username: string;
  email: string;
  firstName: string;
  lastName: string;
  role: CreateUserRole;
}

export type UserCreateDraftField = keyof UserCreateDraft;
export type UserCreateDraftAction = { type: "change"; field: UserCreateDraftField; value: string } | { type: "reset" };

export const emptyUserCreateDraft: UserCreateDraft = {
  username: "",
  email: "",
  firstName: "",
  lastName: "",
  role: "reader",
};

export function userCreateDraftReducer(state: UserCreateDraft, action: UserCreateDraftAction): UserCreateDraft {
  if (action.type === "reset") return emptyUserCreateDraft;
  return { ...state, [action.field]: action.value } as UserCreateDraft;
}

export function createUserInputFromDraft(draft: UserCreateDraft): CreateUserInput {
  return {
    username: draft.username,
    email: draft.email,
    firstName: draft.firstName,
    lastName: draft.lastName,
    role: draft.role,
  };
}
