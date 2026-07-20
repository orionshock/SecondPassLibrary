import { describe, expect, it } from "vitest";

import { displayUserRole } from "../domain/users/presentation";

describe("displayUserRole", () => {
  it("presents Owner as the highest role regardless of the separate API role field", () => {
    expect(displayUserRole({ role: "manager", isOwner: true })).toBe("Owner");
  });

  it("presents the assigned role for non-owners", () => {
    expect(displayUserRole({ role: "manager", isOwner: false })).toBe("Manager");
    expect(displayUserRole({ role: "reader", isOwner: false })).toBe("Reader");
  });
});
