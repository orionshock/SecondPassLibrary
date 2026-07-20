import { ApiError, type ChangeCurrentUserPasswordInput } from "@second-pass/spl-api";

export type PasswordDraft = ChangeCurrentUserPasswordInput;
export type PasswordAction = { type: "change"; field: keyof PasswordDraft; value: string } | { type: "reset" };
export const emptyPasswordDraft: PasswordDraft = { currentPassword: "", newPassword: "", confirmPassword: "" };

export function passwordDraftReducer(state: PasswordDraft, action: PasswordAction): PasswordDraft {
  return action.type === "reset" ? emptyPasswordDraft : { ...state, [action.field]: action.value };
}

export function passwordConfirmationError(draft: PasswordDraft): ApiError | undefined {
  return draft.newPassword === draft.confirmPassword
    ? undefined
    : new ApiError("Passwords do not match.", 400, { fields: { confirm_password: ["Passwords do not match."] } });
}

export function passwordCancelVisible(mustChangePassword: boolean): boolean { return !mustChangePassword; }
