import { describe, expect, it } from "vitest";

import { emptyPasswordDraft, passwordCancelVisible, passwordConfirmationError, passwordDraftReducer } from "../features/password-change/passwordChangeForm";

describe("password change workflow", () => {
  it("rejects a confirmation mismatch", () => {
    expect(passwordConfirmationError({ currentPassword: "old", newPassword: "one", confirmPassword: "two" })?.fields?.confirm_password).toEqual(["Passwords do not match."]);
  });
  it("clears all password fields", () => {
    expect(passwordDraftReducer({ currentPassword: "old", newPassword: "new", confirmPassword: "new" }, { type: "reset" })).toEqual(emptyPasswordDraft);
  });
  it("hides cancel during a forced password change", () => {
    expect(passwordCancelVisible(true)).toBe(false);
    expect(passwordCancelVisible(false)).toBe(true);
  });
});
