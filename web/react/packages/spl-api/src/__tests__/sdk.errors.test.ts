import { describe, expect, it } from "vitest";

import {
  ApiError,
  NetworkError,
  apiErrorFromPayload,
  classifyApiError,
  isAuthenticationError,
} from "../errors";

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

  it("classifies authentication, validation, network, and unknown failures", () => {
    expect(classifyApiError(new ApiError("Signed out", 401))).toBe("authentication");
    expect(classifyApiError(new ApiError("Forbidden", 403))).toBe("authentication");
    expect(classifyApiError(new ApiError("Invalid", 400))).toBe("validation");
    expect(classifyApiError(new NetworkError())).toBe("network");
    expect(classifyApiError(new Error("Unexpected"))).toBe("unknown");
    expect(isAuthenticationError(new ApiError("Signed out", 401))).toBe(true);
  });

  it("normalizes DRF field errors without treating detail as a field", () => {
    const error = apiErrorFromPayload(400, {
      current_password: ["Current password is incorrect."],
      detail: "Invalid password.",
    });

    expect(error.fields).toEqual({ currentPassword: ["Current password is incorrect."] });
  });

  it("preserves flat and nested identifier field errors", () => {
    const nested = apiErrorFromPayload(400, {
      identifiers: [
        { scheme: ["Choose a valid scheme."], value: ["Enter a value."] },
      ],
    });
    const section = apiErrorFromPayload(400, {
      identifiers: ["Duplicate identifiers are not allowed."],
    });

    expect(nested.fields).toEqual({
      "identifiers.0.scheme": ["Choose a valid scheme."],
      "identifiers.0.value": ["Enter a value."],
    });
    expect(section.fields).toEqual({
      identifiers: ["Duplicate identifiers are not allowed."],
    });
  });
});
