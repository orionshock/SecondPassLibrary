import { canSeeImports, canSeeServerSettings, canSeeUsers, isAtLeastLibrarian, type CurrentUser } from "@second-pass/spl-api";
import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { RoleRouteGuardComponent } from "./navigation/RoleRouteGuardComponent";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";
import { GroupDetailOrchestrator } from "../features/groups/GroupDetailOrchestrator";
import { GroupsListOrchestrator } from "../features/groups/GroupsListOrchestrator";
import { ImportsOrchestrator } from "../features/imports/ImportsOrchestrator";
import { BookDetailOrchestrator } from "../features/library/BookDetailOrchestrator";
import { BookEditOrchestrator } from "../features/library/BookEditOrchestrator";
import { AuthorSeriesEditOrchestrator } from "../features/library/AuthorSeriesEditOrchestrator";
import { LibraryOrchestrator } from "../features/library/LibraryOrchestrator";
import { ProfileOrchestrator } from "../features/profile/ProfileOrchestrator";
import { ClientPairingOrchestrator } from "../features/profile/ClientPairingOrchestrator";
import { PasswordChangeOrchestrator } from "../features/password-change/PasswordChangeOrchestrator";
import { ServerSettingsOrchestrator } from "../features/server-settings/ServerSettingsOrchestrator";
import { ShelfCreateOrchestrator } from "../features/shelves/ShelfCreateOrchestrator";
import { ShelfDetailOrchestrator } from "../features/shelves/ShelfDetailOrchestrator";
import { ShelfEditOrchestrator } from "../features/shelves/ShelfEditOrchestrator";
import { ShelvesListOrchestrator } from "../features/shelves/ShelvesListOrchestrator";
import { UserEditOrchestrator } from "../features/users/UserEditOrchestrator";
import { UserCreateOrchestrator } from "../features/users/UserCreateOrchestrator";
import { UsersListOrchestrator } from "../features/users/UsersListOrchestrator";

export const sectionRoutes = [
  { path: "reading", title: "My Marginalia" },
] as const;

const advancedGroupsRouteAvailable = (user: CurrentUser) => user.advancedLibraryGroupsEnabled;

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
      { path: "groups", element: <RoleRouteGuardComponent canAccess={advancedGroupsRouteAvailable}><GroupsListOrchestrator /></RoleRouteGuardComponent> },
      { path: "groups/:groupId", element: <RoleRouteGuardComponent canAccess={advancedGroupsRouteAvailable}><GroupDetailOrchestrator /></RoleRouteGuardComponent> },
      { path: "shelves", element: <ShelvesListOrchestrator /> },
      { path: "shelves/new", element: <ShelfCreateOrchestrator /> },
      { path: "shelves/:shelfId/edit", element: <ShelfEditOrchestrator /> },
      { path: "shelves/:shelfId", element: <ShelfDetailOrchestrator /> },
      { path: "library", element: <LibraryOrchestrator /> },
      { path: "library/books/:bookId", element: <BookDetailOrchestrator /> },
      { path: "library/books/:bookId/edit", element: <RoleRouteGuardComponent canAccess={isAtLeastLibrarian}><BookEditOrchestrator /></RoleRouteGuardComponent> },
      { path: "library/authors/new", element: <RoleRouteGuardComponent canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="author" mode="new" /></RoleRouteGuardComponent> },
      { path: "library/authors/:authorId/edit", element: <RoleRouteGuardComponent canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="author" mode="edit" /></RoleRouteGuardComponent> },
      { path: "library/series/new", element: <RoleRouteGuardComponent canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="series" mode="new" /></RoleRouteGuardComponent> },
      { path: "library/series/:seriesId/edit", element: <RoleRouteGuardComponent canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="series" mode="edit" /></RoleRouteGuardComponent> },
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
