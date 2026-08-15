import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { UserInlineIdentity } from "../../../src/shared/users/UserInlineIdentity";

describe("UserInlineIdentity", () => {
  it("renders full name, plain username, and person identity semantics", () => {
    const markup = renderToStaticMarkup(<UserInlineIdentity username="reader" displayName="Read Er" />);

    expect(markup).toContain('aria-label="User reader"');
    expect(markup).toContain("Read Er");
    expect(markup).toContain(">reader<");
    expect(markup).not.toContain("@reader");
    expect(markup).toContain('aria-hidden="true"');
  });

  it("renders compact username identity without inventing a display name", () => {
    const markup = renderToStaticMarkup(<UserInlineIdentity username="reader" />);

    expect(markup).toContain(">reader<");
    expect(markup).not.toContain("display-name");
  });
});

