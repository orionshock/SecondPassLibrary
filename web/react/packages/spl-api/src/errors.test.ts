import { describe, expect, it } from "vitest";

import { apiErrorFromPayload } from "./errors";

describe("apiErrorFromPayload", () => {
  it("normalizes structured server errors", () => {
    const error = apiErrorFromPayload(400, {
      detail: "Check the submitted fields.",
      code: "validation_error",
      errors: { email: ["Enter a valid email address."] },
    });

    expect(error.status).toBe(400);
    expect(error.message).toBe("Check the submitted fields.");
    expect(error.code).toBe("validation_error");
    expect(error.fields).toEqual({ email: ["Enter a valid email address."] });
  });
});
