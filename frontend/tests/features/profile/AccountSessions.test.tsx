import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { breadcrumbNavigationState } from "../../../src/app/navigation/breadcrumbs";
import { clientPairingBreadcrumbFallback } from "../../../src/app/navigation/accountBreadcrumbs";
import { AccountSessionsPageRegion } from "../../../src/features/profile/regions/AccountSessionsPageRegion";

describe("AccountSessionsPageRegion", () => {
  it("renders connected client metadata and the standard revoke control", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AccountSessionsPageRegion sessions={[{ id: "one", name: "Phone", clientType: "reader", createdAt: "created", updatedAt: "updated" }]} loading={false} clientState={{ pending: false }} bulkClientState={{ pending: false }} webState={{ pending: false }} clientPairingLinkState={breadcrumbNavigationState(clientPairingBreadcrumbFallback)} onLogoutOthers={vi.fn()} onRevokeAllSessions={vi.fn()} onRevokeSession={vi.fn()} /></MemoryRouter>);
    expect(markup).toContain("Phone");
    expect(markup).toContain(">delete</span>");
    expect(markup).toContain("Connect a Device/App");
    expect(markup).toMatch(/<button[^>]*>Disconnect All Devices\/Apps<\/button>/);
  });

  it("disables bulk device disconnection when no active client sessions exist", () => {
    const markup = renderToStaticMarkup(<MemoryRouter><AccountSessionsPageRegion sessions={[]} loading={false} clientState={{ pending: false }} bulkClientState={{ pending: false }} webState={{ pending: false }} clientPairingLinkState={breadcrumbNavigationState(clientPairingBreadcrumbFallback)} onLogoutOthers={vi.fn()} onRevokeAllSessions={vi.fn()} onRevokeSession={vi.fn()} /></MemoryRouter>);
    expect(markup).toMatch(/<button[^>]*disabled=""[^>]*>Disconnect All Devices\/Apps<\/button>/);
  });
});
