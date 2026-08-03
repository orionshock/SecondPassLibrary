import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import { UserInlineIdentityComponent } from "../shared/users/UserInlineIdentityComponent";

describe("UserInlineIdentityComponent", () => {
  it("renders full name, plain username, and person identity semantics", () => {
    const markup = renderToStaticMarkup(<UserInlineIdentityComponent username="reader" displayName="Read Er" />);

    expect(markup).toContain('aria-label="User reader"');
    expect(markup).toContain("Read Er");
    expect(markup).toContain(">reader<");
    expect(markup).not.toContain("@reader");
    expect(markup).toContain('aria-hidden="true"');
  });

  it("renders compact username identity without inventing a display name", () => {
    const markup = renderToStaticMarkup(<UserInlineIdentityComponent username="reader" />);

    expect(markup).toContain(">reader<");
    expect(markup).not.toContain("display-name");
  });
});
