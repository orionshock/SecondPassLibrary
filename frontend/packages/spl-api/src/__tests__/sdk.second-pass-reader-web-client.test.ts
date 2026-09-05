import { describe, expect, it } from "vitest";

import { buildSecondPassReaderBookUrl } from "../secondPassReaderWebClientUrl";

describe("Second Pass Reader web client launcher", () => {
  it("builds a hash-reader URL and defensively removes trailing slashes", () => {
    expect(buildSecondPassReaderBookUrl(
      "https://reader.example.com///",
      "7152f4b8-ad35-4dd6-9e40-8ae68678e76e",
    )).toBe(
      "https://reader.example.com/#/reader/7152f4b8-ad35-4dd6-9e40-8ae68678e76e",
    );
  });

  it("encodes the book identifier without interpreting templates", () => {
    expect(buildSecondPassReaderBookUrl("https://reader.example.com", "book/id?{raw}"))
      .toBe("https://reader.example.com/#/reader/book%2Fid%3F%7Braw%7D");
  });

  it("rejects noncanonical and template base URLs", () => {
    expect(() => buildSecondPassReaderBookUrl("https://reader.example.com/app", "book"))
      .toThrow("canonical HTTP(S) base URL");
    expect(() => buildSecondPassReaderBookUrl("https://reader.example.com/{book}", "book"))
      .toThrow("templates");
  });
});
