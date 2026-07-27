import { canSeeImports, canSeeServerSettings, canSeeUsers, isAtLeastLibrarian, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";
import { createBrowserRouter } from "react-router-dom";

import { App } from "./App";
import { RoleRouteGuardComponent } from "./navigation/RoleRouteGuardComponent";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";
import { GroupDetailOrchestrator } from "../features/groups/GroupDetailOrchestrator";
import { GroupCreateOrchestrator } from "../features/groups/GroupCreateOrchestrator";
import { GroupEditOrchestrator } from "../features/groups/GroupEditOrchestrator";
import { GroupsListOrchestrator } from "../features/groups/GroupsListOrchestrator";
import { canCreateGroupMetadata } from "../features/groups/groupMetadataAuthority";
import { ImportsOrchestrator } from "../features/imports/ImportsOrchestrator";
import { BookDetailOrchestrator } from "../features/library/BookDetailOrchestrator";
import { BookEditOrchestrator } from "../features/library/BookEditOrchestrator";
import { AuthorSeriesEditOrchestrator } from "../features/library/AuthorSeriesEditOrchestrator";
import { LibraryOrchestrator } from "../features/library/LibraryOrchestrator";
import { ProfileOrchestrator } from "../features/profile/ProfileOrchestrator";
import { ReadingSessionsOrchestrator } from "../features/reading/ReadingSessionsOrchestrator";
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
import { ProductPageShellComponent } from "../shared/layout/ProductPageShellComponent";

export const sectionRoutes = [] as const;

const advancedGroupsRouteAvailable = (_user: CurrentUser, server: ServerInfo) => server.advancedLibraryGroupsEnabled;
const groupCreationRouteAvailable = (user: CurrentUser, server: ServerInfo) => (
  canCreateGroupMetadata(user, server.advancedLibraryGroupsEnabled)
);

export function PlaceholderPageRegion({ title }: { title: string }) {
  return <ProductPageShellComponent eyebrow="React Product UI" title={title}>
    <section className="page-panel">
      <p>This section has not been rebuilt yet.</p>
    </section>
  </ProductPageShellComponent>;
}

export function NotFoundPageRegion() {
  return <ProductPageShellComponent eyebrow="Not found" title="Page not found">
    <section className="page-panel">
      <p>This address does not match a Product UI page.</p>
    </section>
  </ProductPageShellComponent>;
}

export const appRoutes = [
  {
    path: "/",
    element: <App />,
    children: [
      { index: true, element: <DashboardOrchestrator /> },
      { path: "reading", element: <ReadingSessionsOrchestrator /> },
      ...sectionRoutes.map(({ path, title }) => ({
        path,
        element: <PlaceholderPageRegion title={title} />,
      })),
      { path: "groups", element: <RoleRouteGuardComponent canAccess={advancedGroupsRouteAvailable}><GroupsListOrchestrator /></RoleRouteGuardComponent> },
      { path: "groups/new", element: <RoleRouteGuardComponent canAccess={groupCreationRouteAvailable}><GroupCreateOrchestrator /></RoleRouteGuardComponent> },
      { path: "groups/:groupId/edit", element: <RoleRouteGuardComponent canAccess={advancedGroupsRouteAvailable}><GroupEditOrchestrator /></RoleRouteGuardComponent> },
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
