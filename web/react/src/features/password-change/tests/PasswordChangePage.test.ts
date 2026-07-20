import { describe, expect, it } from "vitest";

import { emptyPasswordDraft, passwordCancelVisible, passwordConfirmationError, passwordDraftReducer } from "../PasswordChangePage";

describe("password change workflow", () => {
  it("rejects a confirmation mismatch before submission", () => {
    const error = passwordConfirmationError({ currentPassword: "old", newPassword: "new-one", confirmPassword: "new-two" });
    expect(error?.fields?.confirm_password).toEqual(["Passwords do not match."]);
  });

  it("clears all password fields on cancel", () => {
    expect(passwordDraftReducer({ currentPassword: "old", newPassword: "new", confirmPassword: "new" }, { type: "reset" })).toEqual(emptyPasswordDraft);
  });

  it("hides cancel during a forced password change", () => {
    expect(passwordCancelVisible(true)).toBe(false);
    expect(passwordCancelVisible(false)).toBe(true);
  });
});
