import { describe, expect, it } from "vitest";
import { ApiError } from "@second-pass/spl-api";

import { LocalValidationError } from "../shared/feedback/mutationState";

import { emptyPasswordDraft, passwordCancelVisible, passwordConfirmationError, passwordDraftReducer } from "../features/password-change/passwordChangeForm";

describe("password change workflow", () => {
  it("rejects a confirmation mismatch", () => {
    const error = passwordConfirmationError({ currentPassword: "old", newPassword: "one", confirmPassword: "two" });
    expect(error).toBeInstanceOf(LocalValidationError);
    expect(error).not.toBeInstanceOf(ApiError);
    expect(error?.fields?.confirmPassword).toEqual(["Passwords do not match."]);
  });
  it("clears all password fields", () => {
    expect(passwordDraftReducer({ currentPassword: "old", newPassword: "new", confirmPassword: "new" }, { type: "reset" })).toEqual(emptyPasswordDraft);
  });
  it("hides cancel during a forced password change", () => {
    expect(passwordCancelVisible(true)).toBe(false);
    expect(passwordCancelVisible(false)).toBe(true);
  });
});
