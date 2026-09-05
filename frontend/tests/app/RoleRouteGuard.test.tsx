import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";

import { canSeeImports, canSeeServerSettings, canSeeUsers, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";
import { AppOrchestrator } from "../../src/app/layout/AppOrchestrator";
import { RoleRouteGuard, unauthorizedRouteFallback } from "../../src/app/navigation/RoleRouteGuard";

const server: ServerInfo = { name: "SPL", description: "", bannerText: "", advancedLibraryGroupsEnabled: false, secondPassReaderWebClientUrl: null, marginaliaProfileUri: "profile", publicGroup: { id: "public", name: "Common Room", description: "" }, version: "dev", releaseDate: "" };
const reader: CurrentUser = {
  username: "reader", email: "", firstName: "", lastName: "", profileId: "reader", role: "reader",
  mustChangePassword: false, isOwner: false, isManager: false, isLibrarian: false, isReader: true,
  canAccessDjangoAdmin: false, groups: [],
};
const librarian: CurrentUser = { ...reader, username: "librarian", role: "librarian", isLibrarian: true, isReader: false };
const manager: CurrentUser = { ...reader, username: "manager", role: "manager", isManager: true, isReader: false };

function renderGuard(user: CurrentUser, canAccess: (user: CurrentUser) => boolean, onFeatureRender: () => void): string {
  function Feature() { onFeatureRender(); return <p>Protected feature</p>; }
  return renderToStaticMarkup(<MemoryRouter initialEntries={["/protected"]}><Routes>
    <Route element={<AppOrchestrator user={user} server={server} onCurrentUserChange={vi.fn()} />}>
      <Route path="protected" element={<RoleRouteGuard canAccess={canAccess}><Feature /></RoleRouteGuard>} />
    </Route>
  </Routes></MemoryRouter>);
}

describe("role-obvious feature route fallback", () => {
  it("does not mount Users for Reader or Librarian operators", () => {
    for (const user of [reader, librarian]) {
      const featureRender = vi.fn();
      expect(renderGuard(user, canSeeUsers, featureRender)).not.toContain("Protected feature");
      expect(featureRender).not.toHaveBeenCalled();
    }
    expect(unauthorizedRouteFallback).toBe("/");
  });

  it("does not mount Imports for Readers or Server Settings for non-Owners", () => {
    const importsRender = vi.fn();
    const serverRender = vi.fn();
    expect(renderGuard(reader, canSeeImports, importsRender)).not.toContain("Protected feature");
    expect(renderGuard(manager, canSeeServerSettings, serverRender)).not.toContain("Protected feature");
    expect(importsRender).not.toHaveBeenCalled();
    expect(serverRender).not.toHaveBeenCalled();
  });

  it("mounts an authorized branch", () => {
    const featureRender = vi.fn();
    expect(renderGuard(manager, canSeeUsers, featureRender)).toContain("Protected feature");
    expect(featureRender).toHaveBeenCalledOnce();
  });
});

