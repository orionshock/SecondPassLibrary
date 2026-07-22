import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";
import { ImportsOrchestrator } from "../features/imports/ImportsOrchestrator";
import { ProfileOrchestrator } from "../features/profile/ProfileOrchestrator";
import { ClientPairingOrchestrator } from "../features/profile/ClientPairingOrchestrator";
import { PasswordChangeOrchestrator } from "../features/password-change/PasswordChangeOrchestrator";
import { ServerSettingsOrchestrator } from "../features/server-settings/ServerSettingsOrchestrator";
import { UserEditOrchestrator } from "../features/users/UserEditOrchestrator";
import { UserCreateOrchestrator } from "../features/users/UserCreateOrchestrator";
import { UsersListOrchestrator } from "../features/users/UsersListOrchestrator";

export const sectionRoutes = [
  { path: "reading", title: "My Marginalia" },
  { path: "library", title: "Library" },
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
      { path: "imports", element: <ImportsOrchestrator /> },
      { path: "profile", element: <ProfileOrchestrator /> },
      { path: "profile/client-pairing", element: <ClientPairingOrchestrator /> },
      { path: "profile/password", element: <PasswordChangeOrchestrator /> },
      { path: "users", element: <UsersListOrchestrator /> },
      { path: "users/new", element: <UserCreateOrchestrator /> },
      { path: "users/:profileId/edit", element: <UserEditOrchestrator /> },
      { path: "server", element: <ServerSettingsOrchestrator /> },
      { path: "*", element: <NotFoundPageRegion /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
