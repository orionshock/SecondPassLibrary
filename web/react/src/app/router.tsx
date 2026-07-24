import { canSeeImports, canSeeServerSettings, canSeeUsers } from "@second-pass/spl-api";
import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { RoleRouteGuardComponent } from "./navigation/RoleRouteGuardComponent";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";
import { ImportsOrchestrator } from "../features/imports/ImportsOrchestrator";
import { BookDetailOrchestrator } from "../features/library/BookDetailOrchestrator";
import { LibraryOrchestrator } from "../features/library/LibraryOrchestrator";
import { ProfileOrchestrator } from "../features/profile/ProfileOrchestrator";
import { ClientPairingOrchestrator } from "../features/profile/ClientPairingOrchestrator";
import { PasswordChangeOrchestrator } from "../features/password-change/PasswordChangeOrchestrator";
import { ServerSettingsOrchestrator } from "../features/server-settings/ServerSettingsOrchestrator";
import { UserEditOrchestrator } from "../features/users/UserEditOrchestrator";
import { UserCreateOrchestrator } from "../features/users/UserCreateOrchestrator";
import { UsersListOrchestrator } from "../features/users/UsersListOrchestrator";

export const sectionRoutes = [
  { path: "reading", title: "My Marginalia" },
  { path: "groups", title: "Groups" },
  { path: "shelves", title: "Shelves" },
] as const;

export function PlaceholderPageRegion({ title }: { title: string }) {
  return (
    <section className="page-panel">
      <p className="eyebrow">React Product UI</p>
      <h1>{title}</h1>
      <p>This section has not been rebuilt yet.</p>
    </section>
  );
}

export function NotFoundPageRegion() {
  return (
    <section className="page-panel">
      <p className="eyebrow">Not found</p>
      <h1>Page not found</h1>
      <p>This address does not match a Product UI page.</p>
    </section>
  );
}

export const appRoutes = [
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <DashboardOrchestrator /> },
      ...sectionRoutes.map(({ path, title }) => ({
        path,
        element: <PlaceholderPageRegion title={title} />,
      })),
      { path: "library", element: <LibraryOrchestrator /> },
      { path: "library/books/:bookId", element: <BookDetailOrchestrator /> },
      { path: "imports", element: <RoleRouteGuardComponent canAccess={canSeeImports}><ImportsOrchestrator /></RoleRouteGuardComponent> },
      { path: "profile", element: <ProfileOrchestrator /> },
      { path: "profile/client-pairing", element: <ClientPairingOrchestrator /> },
      { path: "profile/password", element: <PasswordChangeOrchestrator /> },
      { path: "users", element: <RoleRouteGuardComponent canAccess={canSeeUsers}><UsersListOrchestrator /></RoleRouteGuardComponent> },
      { path: "users/new", element: <RoleRouteGuardComponent canAccess={canSeeUsers}><UserCreateOrchestrator /></RoleRouteGuardComponent> },
      { path: "users/:profileId/edit", element: <RoleRouteGuardComponent canAccess={canSeeUsers}><UserEditOrchestrator /></RoleRouteGuardComponent> },
      { path: "server", element: <RoleRouteGuardComponent canAccess={canSeeServerSettings}><ServerSettingsOrchestrator /></RoleRouteGuardComponent> },
      { path: "*", element: <NotFoundPageRegion /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
