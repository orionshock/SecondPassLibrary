import { describe, expect, it } from "vitest";

import {
  ApiError,
  NetworkError,
  apiErrorFromPayload,
  classifyApiError,
  isAuthenticationError,
} from "../../packages/spl-api/src/errors";

describe("apiErrorFromPayload", () => {
  it("preserves structured import error arrays without promoting raw paths to the message", () => {
    const error = apiErrorFromPayload(400, {
      valid: false,
      errors: [
        { path: "$.file", message: "Upload a JSON file." },
        { path: "$.import_token", message: "Import preview expired." },
        { path: "$.books[0].sessions[0]", message: "Session is invalid." },
      ],
    });
    expect(error.message).toContain("try again");
    expect(error.message).not.toContain("$.books");
    expect(error.fields).toEqual({
      file: ["Upload a JSON file."],
      importToken: ["Import preview expired."],
      "books[0].sessions[0]": ["Session is invalid."],
    });
  });
  it("does not promote arbitrary DRF detail into the user message", () => {
    const error = apiErrorFromPayload(400, {
      detail: "Check the submitted fields.",
      code: "validation_error",
      errors: { email: ["Enter a valid email address."] },
    });

    expect(error.status).toBe(400);
    expect(error.message).toContain("highlighted fields");
    expect(error.message).not.toContain("submitted fields");
    expect(error.code).toBe("validation_error");
    expect(error.fields).toEqual({ email: ["Enter a valid email address."] });
  });

  it("normalizes the bounded project error envelope", () => {
    const error = apiErrorFromPayload(409, {
      error: {
        code: "SESSION_CLOSED",
        message: "The Reading Session is closed.",
        detail: "",
        hint: "",
      },
    });

    expect(error.status).toBe(409);
    expect(error.message).toBe("The Reading Session is closed.");
    expect(error.code).toBe("SESSION_CLOSED");
    expect(error.fields).toBeUndefined();
  });

  it("keeps the bounded project recovery hint with its stable category", () => {
    const error = apiErrorFromPayload(409, {
      error: {
        code: "IMPORT_CONFLICT",
        message: "The import conflicts with existing data.",
        hint: "Review the conflict and import again.",
      },
    });

    expect(error).toMatchObject({ status: 409, code: "IMPORT_CONFLICT" });
    expect(error.message).toContain("Review the conflict and import again.");
  });

  it("normalizes Author and Series attachment conflicts without treating bounded details as fields", () => {
    for (const [code, message] of [
      ["author_has_books", "Author cannot be deleted because 2 Books are attached."],
      ["series_has_books", "Series cannot be deleted because 1 Book is attached."],
    ]) {
      const error = apiErrorFromPayload(409, {
        error: { code, message, details: { book_count: 2 } },
      });
      expect(error).toMatchObject({ status: 409, code, message });
      expect(error.fields).toBeUndefined();
    }
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
