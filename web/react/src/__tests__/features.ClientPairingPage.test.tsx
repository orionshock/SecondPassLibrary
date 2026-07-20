import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ClientPairingPage, PairingCompletion } from "../features/profile/ClientPairingPage";

describe("client pairing completion", () => {
  it("offers clear exits without rendering pairing inputs", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter><PairingCompletion message="Client authorized." /></MemoryRouter>,
    );

    expect(markup).toContain('href="/profile"');
    expect(markup).toContain('href="/"');
    expect(markup).not.toContain("pairing-code");
    expect(markup).not.toContain("Continue");
    expect(markup).toContain("form-action-row");
    expect(markup.indexOf("Go to Home")).toBeLessThan(markup.indexOf("Back to Profile"));
  });

  it("right-aligns the initial workflow action", () => {
    const markup = renderToStaticMarkup(
      <MemoryRouter><ClientPairingPage /></MemoryRouter>,
    );

    expect(markup).toContain("Continue");
    expect(markup).toContain("form-action-row");
  });
});
