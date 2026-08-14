import { canSeeImports, canSeeServerSettings, canSeeUsers, isAtLeastLibrarian, type CurrentUser, type ServerInfo } from "@second-pass/spl-api";
import { lazy } from "react";
import { createBrowserRouter } from "react-router";

import { App } from "./App";
import { RoleRouteGuard } from "./navigation/RoleRouteGuard";
import { DashboardOrchestrator } from "../features/dashboard/DashboardOrchestrator";
import { canCreateGroupMetadata } from "../features/groups/groupMetadataAuthority";
import { ProductPageShellComponent } from "../shared/layout/ProductPageShellComponent";

const LibraryOrchestrator = lazy(() => import("./routes/libraryRoutes").then((module) => ({ default: module.LibraryOrchestrator })));
const BookDetailOrchestrator = lazy(() => import("./routes/libraryRoutes").then((module) => ({ default: module.BookDetailOrchestrator })));
const BookEditOrchestrator = lazy(() => import("./routes/libraryMutationRoutes").then((module) => ({ default: module.BookEditOrchestrator })));
const AuthorSeriesEditOrchestrator = lazy(() => import("./routes/libraryMutationRoutes").then((module) => ({ default: module.AuthorSeriesEditOrchestrator })));

const MarginaliaSessionsOrchestrator = lazy(() => import("./routes/marginaliaRoutes").then((module) => ({ default: module.MarginaliaSessionsOrchestrator })));
const MarginaliaSessionDetailOrchestrator = lazy(() => import("./routes/marginaliaRoutes").then((module) => ({ default: module.MarginaliaSessionDetailOrchestrator })));
const MarginaliaImportOrchestrator = lazy(() => import("./routes/marginaliaTransferRoutes").then((module) => ({ default: module.MarginaliaImportOrchestrator })));
const MarginaliaExportOrchestrator = lazy(() => import("./routes/marginaliaTransferRoutes").then((module) => ({ default: module.MarginaliaExportOrchestrator })));

const ShelvesListOrchestrator = lazy(() => import("./routes/shelvesRoutes").then((module) => ({ default: module.ShelvesListOrchestrator })));
const ShelfCreateOrchestrator = lazy(() => import("./routes/shelvesRoutes").then((module) => ({ default: module.ShelfCreateOrchestrator })));
const ShelfDetailOrchestrator = lazy(() => import("./routes/shelvesRoutes").then((module) => ({ default: module.ShelfDetailOrchestrator })));
const ShelfEditOrchestrator = lazy(() => import("./routes/shelvesRoutes").then((module) => ({ default: module.ShelfEditOrchestrator })));

const GroupsListOrchestrator = lazy(() => import("./routes/groupsRoutes").then((module) => ({ default: module.GroupsListOrchestrator })));
const GroupDetailOrchestrator = lazy(() => import("./routes/groupsRoutes").then((module) => ({ default: module.GroupDetailOrchestrator })));
const GroupCreateOrchestrator = lazy(() => import("./routes/groupManagementRoutes").then((module) => ({ default: module.GroupCreateOrchestrator })));
const GroupEditOrchestrator = lazy(() => import("./routes/groupManagementRoutes").then((module) => ({ default: module.GroupEditOrchestrator })));

const ProfileOrchestrator = lazy(() => import("./routes/profileRoutes").then((module) => ({ default: module.ProfileOrchestrator })));
const ClientPairingOrchestrator = lazy(() => import("./routes/profileRoutes").then((module) => ({ default: module.ClientPairingOrchestrator })));
const PasswordChangeOrchestrator = lazy(() => import("./routes/profileRoutes").then((module) => ({ default: module.PasswordChangeOrchestrator })));

const ImportsOrchestrator = lazy(() => import("./routes/administrationRoutes").then((module) => ({ default: module.ImportsOrchestrator })));
const UsersListOrchestrator = lazy(() => import("./routes/administrationRoutes").then((module) => ({ default: module.UsersListOrchestrator })));
const UserCreateOrchestrator = lazy(() => import("./routes/administrationRoutes").then((module) => ({ default: module.UserCreateOrchestrator })));
const UserEditOrchestrator = lazy(() => import("./routes/administrationRoutes").then((module) => ({ default: module.UserEditOrchestrator })));
const ServerSettingsOrchestrator = lazy(() => import("./routes/administrationRoutes").then((module) => ({ default: module.ServerSettingsOrchestrator })));

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
      { path: "marginalia", element: <MarginaliaSessionsOrchestrator /> },
      { path: "marginalia/sessions/:sessionId", element: <MarginaliaSessionDetailOrchestrator /> },
      { path: "marginalia/import", element: <MarginaliaImportOrchestrator /> },
      { path: "marginalia/export", element: <MarginaliaExportOrchestrator /> },
      ...sectionRoutes.map(({ path, title }) => ({
        path,
        element: <PlaceholderPageRegion title={title} />,
      })),
      { path: "groups", element: <RoleRouteGuard canAccess={advancedGroupsRouteAvailable}><GroupsListOrchestrator /></RoleRouteGuard> },
      { path: "groups/new", element: <RoleRouteGuard canAccess={groupCreationRouteAvailable}><GroupCreateOrchestrator /></RoleRouteGuard> },
      { path: "groups/:groupId/edit", element: <RoleRouteGuard canAccess={advancedGroupsRouteAvailable}><GroupEditOrchestrator /></RoleRouteGuard> },
      { path: "groups/:groupId", element: <RoleRouteGuard canAccess={advancedGroupsRouteAvailable}><GroupDetailOrchestrator /></RoleRouteGuard> },
      { path: "shelves", element: <ShelvesListOrchestrator /> },
      { path: "shelves/new", element: <ShelfCreateOrchestrator /> },
      { path: "shelves/:shelfId/edit", element: <ShelfEditOrchestrator /> },
      { path: "shelves/:shelfId", element: <ShelfDetailOrchestrator /> },
      { path: "library", element: <LibraryOrchestrator /> },
      { path: "library/books/:bookId", element: <BookDetailOrchestrator /> },
      { path: "library/books/:bookId/edit", element: <RoleRouteGuard canAccess={isAtLeastLibrarian}><BookEditOrchestrator /></RoleRouteGuard> },
      { path: "library/authors/new", element: <RoleRouteGuard canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="author" mode="new" /></RoleRouteGuard> },
      { path: "library/authors/:authorId/edit", element: <RoleRouteGuard canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="author" mode="edit" /></RoleRouteGuard> },
      { path: "library/series/new", element: <RoleRouteGuard canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="series" mode="new" /></RoleRouteGuard> },
      { path: "library/series/:seriesId/edit", element: <RoleRouteGuard canAccess={isAtLeastLibrarian}><AuthorSeriesEditOrchestrator kind="series" mode="edit" /></RoleRouteGuard> },
      { path: "imports", element: <RoleRouteGuard canAccess={canSeeImports}><ImportsOrchestrator /></RoleRouteGuard> },
      { path: "profile", element: <ProfileOrchestrator /> },
      { path: "profile/client-pairing", element: <ClientPairingOrchestrator /> },
      { path: "profile/password", element: <PasswordChangeOrchestrator /> },
      { path: "users", element: <RoleRouteGuard canAccess={canSeeUsers}><UsersListOrchestrator /></RoleRouteGuard> },
      { path: "users/new", element: <RoleRouteGuard canAccess={canSeeUsers}><UserCreateOrchestrator /></RoleRouteGuard> },
      { path: "users/:profileId/edit", element: <RoleRouteGuard canAccess={canSeeUsers}><UserEditOrchestrator /></RoleRouteGuard> },
      { path: "server", element: <RoleRouteGuard canAccess={canSeeServerSettings}><ServerSettingsOrchestrator /></RoleRouteGuard> },
      { path: "*", element: <NotFoundPageRegion /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
