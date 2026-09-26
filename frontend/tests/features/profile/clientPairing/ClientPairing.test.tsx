import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { PairingCompletionPageRegion } from "../../../../src/features/profile/clientPairing/PairingCompletionPageRegion";
import { PairingRequestPageRegion } from "../../../../src/features/profile/clientPairing/PairingRequestPageRegion";

describe("client pairing regions", () => {
  it("offers completion exits without pairing inputs", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><PairingCompletionPageRegion message="Client authorized." /></MemoryRouter>);
    expect(markup).toContain('href="/profile"');
    expect(markup).toContain('href="/"');
    expect(markup).not.toContain("pairing-code");
  });
  it("renders the initial lookup action", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><PairingRequestPageRegion code="" clientName="" pending={false} onCodeChange={vi.fn()} onClientNameChange={vi.fn()} onLookup={vi.fn()} onDecision={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain("Continue");
  });
});

