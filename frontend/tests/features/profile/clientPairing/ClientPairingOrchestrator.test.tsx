/** @vitest-environment happy-dom */

import { act } from "react";
import { createRoot } from "react-dom/client";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

const sdk = vi.hoisted(() => ({ lookup: vi.fn(), decide: vi.fn() }));
vi.mock("@second-pass/spl-api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@second-pass/spl-api")>()),
  lookupClientPairing: sdk.lookup,
  decideClientPairing: sdk.decide,
}));

vi.mock("../../../../src/app/navigation/usePageBreadcrumbs", () => ({ usePageBreadcrumbs: vi.fn() }));

import { ClientPairingOrchestrator } from "../../../../src/features/profile/clientPairing/ClientPairingOrchestrator";

(globalThis as typeof globalThis & { IS_REACT_ACT_ENVIRONMENT: boolean }).IS_REACT_ACT_ENVIRONMENT = true;
let root: ReturnType<typeof createRoot> | undefined;

afterEach(async () => {
  if (root) await act(async () => root?.unmount());
  root = undefined;
  document.body.replaceChildren();
  vi.clearAllMocks();
});

async function mount(path = "/profile/pair?code=PAIR-123") {
  const container = document.createElement("div");
  document.body.append(container);
  root = createRoot(container);
  await act(async () => root?.render(<MemoryRouter initialEntries={[path]}><ClientPairingOrchestrator /></MemoryRouter>));
  return container;
}

describe("ClientPairingOrchestrator", () => {
  it("loads the URL request and approves the displayed client", async () => {
    sdk.lookup.mockResolvedValue({ code: "PAIR-123", clientName: "Web Reader", clientType: "web" });
    sdk.decide.mockResolvedValue("approved");

    const container = await mount();
    expect(sdk.lookup).toHaveBeenCalledWith("PAIR-123");
    expect(container.querySelector<HTMLInputElement>("#pairing-client-name")?.value).toBe("Web Reader");

    const approve = Array.from(container.querySelectorAll("button")).find((button) => button.textContent === "Approve")!;
    await act(async () => approve.click());

    expect(sdk.decide).toHaveBeenCalledWith({ code: "PAIR-123", action: "approve", clientName: "Web Reader" });
    expect(container.querySelector("form")).toBeNull();
  });

  it("shows lookup failure and permits a retry without stale request details", async () => {
    sdk.lookup.mockRejectedValueOnce(new Error("Pairing code expired."));
    const container = await mount();

    expect(container.textContent).toContain("Pairing code expired.");
    expect(container.querySelector("#pairing-client-name")).toBeNull();

    sdk.lookup.mockResolvedValueOnce({ code: "PAIR-123", clientName: "Retry Reader", clientType: "web" });
    const form = container.querySelector("form")!;
    await act(async () => form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true })));
    expect(container.querySelector<HTMLInputElement>("#pairing-client-name")?.value).toBe("Retry Reader");
  });
});
