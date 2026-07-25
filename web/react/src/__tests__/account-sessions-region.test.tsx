import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { breadcrumbNavigationState } from "../app/navigation/breadcrumbs";
import { AccountSessionsPageRegion } from "../features/profile/regions/AccountSessionsPageRegion";
import { clientPairingBreadcrumbFallback } from "../features/profile/profileBreadcrumbs";
import { confirmClientSessionRevoke, confirmLogoutOtherWebSessions } from "../features/profile/profileConfirmations";

describe("AccountSessionsPageRegion", () => {
  it("renders connected client metadata and the standard revoke control", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AccountSessionsPageRegion sessions={[{ id: "one", name: "Phone", clientType: "reader", createdAt: "created", updatedAt: "updated" }]} loading={false} clientState={{ pending: false }} webState={{ pending: false }} clientPairingLinkState={breadcrumbNavigationState(clientPairingBreadcrumbFallback)} onLogoutOthers={vi.fn()} onRevokeSession={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain("Phone");
    expect(markup).toContain(">delete</span>");
    expect(markup).toContain("Connect a Device/App");
  });

  it("preserves confirmations for destructive session actions", () => {
    const revokeConfirm = vi.fn(() => false);
    const logoutConfirm = vi.fn(() => false);
    expect(confirmClientSessionRevoke("Living Room Reader", revokeConfirm)).toBe(false);
    expect(confirmLogoutOtherWebSessions(logoutConfirm)).toBe(false);
    expect(revokeConfirm).toHaveBeenCalledWith(expect.stringContaining("Living Room Reader"));
    expect(logoutConfirm).toHaveBeenCalledWith(expect.stringContaining("all other web sessions"));
  });
});
