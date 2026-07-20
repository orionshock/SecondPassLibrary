import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { DashboardPage } from "../features/dashboard/DashboardPage";
import { ProfilePage } from "../features/profile/ProfilePage";
import { ClientPairingPage } from "../features/profile/ClientPairingPage";
import { PasswordChangePage } from "../features/password-change/PasswordChangePage";

export const sectionRoutes = [
  { path: "reading", title: "My Marginalia" },
  { path: "library", title: "Library" },
  { path: "groups", title: "Groups" },
  { path: "shelves", title: "Shelves" },
  { path: "users", title: "Users" },
  { path: "imports", title: "Imports" },
  { path: "server", title: "Server Settings" },
] as const;

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <section className="page-panel">
      <p className="eyebrow">React Product UI</p>
      <h1>{title}</h1>
      <p>This section has not been rebuilt yet.</p>
    </section>
  );
}

export function NotFoundPage() {
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
      { index: true, element: <DashboardPage /> },
      ...sectionRoutes.map(({ path, title }) => ({
        path,
        element: <PlaceholderPage title={title} />,
      })),
      { path: "profile", element: <ProfilePage /> },
      { path: "profile/client-pairing", element: <ClientPairingPage /> },
      { path: "profile/password", element: <PasswordChangePage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
