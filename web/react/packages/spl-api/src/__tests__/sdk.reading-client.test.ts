import { describe, expect, it } from "vitest";

import { buildReadingClientBookUrl } from "../readingClient";

describe("Reading Client launcher", () => {
  it("builds a hash-reader URL and defensively removes trailing slashes", () => {
    expect(buildReadingClientBookUrl(
      "https://reader.example.com///",
      "7152f4b8-ad35-4dd6-9e40-8ae68678e76e",
    )).toBe(
      "https://reader.example.com/#/reader/7152f4b8-ad35-4dd6-9e40-8ae68678e76e",
    );
  });

  it("encodes the book identifier without interpreting templates", () => {
    expect(buildReadingClientBookUrl("https://reader.example.com", "book/id?{raw}"))
      .toBe("https://reader.example.com/#/reader/book%2Fid%3F%7Braw%7D");
  });

  it("rejects path-mounted and template base URLs", () => {
    expect(() => buildReadingClientBookUrl("https://reader.example.com/app", "book"))
      .toThrow("root URL");
    expect(() => buildReadingClientBookUrl("https://reader.example.com/{book}", "book"))
      .toThrow("templates");
  });
});
