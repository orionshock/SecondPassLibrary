import {
  canSeeImports,
  canSeeServerSettings,
  canSeeUsers,
  logoutCurrentWebSession,
  type CurrentUser,
  type ServerInfo,
} from "@second-pass/spl-api";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { Link, Outlet, useLocation } from "react-router";

import { BreadcrumbsComponent } from "../navigation/BreadcrumbsComponent";
import type { BreadcrumbItem } from "../navigation/breadcrumbs";
import { MaterialIcon } from "../../components/icons/MaterialIcon";
import { ErrorPanel } from "../../components/UiPrimitives";
import { RouteModuleBoundary, RouteModuleLoading } from "../routing/RouteModuleBoundary";
import { AppMenuComponent, type AppMenuItem } from "./AppMenuComponent";
import "./AppOrchestrator.css";

export interface AppOutletContext {
  currentUser: CurrentUser;
  serverInfo: ServerInfo;
  onCurrentUserChange: (user: CurrentUser) => void;
  refreshCurrentUser: () => Promise<CurrentUser>;
  refreshServerInfo: () => Promise<ServerInfo>;
  setBreadcrumbs: (pathname: string, items: readonly BreadcrumbItem[]) => void;
}

interface NavigationDestination {
  to: string;
  label: string;
  icon: string;
  visible?: (user: CurrentUser, server: ServerInfo) => boolean;
}

export const primaryNavigation: readonly NavigationDestination[] = [
  { to: "/marginalia", label: "My Marginalia", icon: "history" },
  { to: "/library", label: "Library", icon: "book_2" },
  { to: "/shelves", label: "Shelves", icon: "shelves" },
  { to: "/groups", label: "Groups", icon: "groups", visible: (_user, server) => server.advancedLibraryGroupsEnabled },
] as const;

export const secondaryNavigation: readonly NavigationDestination[] = [
  { to: "/imports", label: "Book Import", icon: "upload_file", visible: canSeeImports },
  { to: "/users", label: "Users", icon: "manage_accounts", visible: canSeeUsers },
  { to: "/server", label: "Server Settings", icon: "settings", visible: canSeeServerSettings },
] as const;

export function navigationDestinationOwnsPath(destination: string, pathname: string): boolean {
  return pathname === destination || pathname.startsWith(`${destination}/`);
}

export function focusRouteHeading(container: HTMLElement | null): boolean {
  const heading = container?.querySelector<HTMLElement>("h1");
  if (!heading) return false;
  heading.tabIndex = -1;
  heading.focus();
  return true;
}

export function accountMenuItems(
  pathname: string,
  onLogout: () => void = () => undefined,
): readonly AppMenuItem[] {
  return [
    {
      key: "profile",
      label: "Profile settings",
      icon: "person",
      to: "/profile",
      active: navigationDestinationOwnsPath("/profile", pathname),
    },
    { key: "logout", label: "Log out", icon: "logout", onSelect: onLogout },
  ];
}

export function AppOrchestrator({
  user,
  server,
  onCurrentUserChange,
  onRefreshCurrentUser = async () => user,
  onRefreshServerInfo = async () => server,
}: {
  user: CurrentUser;
  server: ServerInfo;
  onCurrentUserChange: (user: CurrentUser) => void;
  onRefreshCurrentUser?: () => Promise<CurrentUser>;
  onRefreshServerInfo?: () => Promise<ServerInfo>;
}) {
  const location = useLocation();
  const mainRef = useRef<HTMLElement>(null);
  const [logoutError, setLogoutError] = useState<string>();
  const [breadcrumbRegistration, setBreadcrumbRegistration] = useState<{ pathname: string; items: readonly BreadcrumbItem[] }>();
  const setBreadcrumbs = useCallback((pathname: string, items: readonly BreadcrumbItem[]) => {
    setBreadcrumbRegistration({ pathname, items });
  }, []);
  const breadcrumbs = breadcrumbRegistration?.pathname === location.pathname ? breadcrumbRegistration.items : [];
  const visiblePrimary = primaryNavigation.filter((item) => !item.visible || item.visible(user, server));
  const visibleSecondary = secondaryNavigation.filter((item) => !item.visible || item.visible(user, server));
  const hasFullNavigation = visiblePrimary.length === primaryNavigation.length
    && visibleSecondary.length === secondaryNavigation.length;
  const overflowItems: AppMenuItem[] = visibleSecondary.map((item) => ({
    key: item.to,
    label: item.label,
    icon: item.icon,
    to: item.to,
    active: navigationDestinationOwnsPath(item.to, location.pathname),
  }));
  const accountActive = navigationDestinationOwnsPath("/profile", location.pathname);
  const logout = useCallback(() => {
    setLogoutError(undefined);
    void logoutCurrentWebSession()
      .then(() => window.location.assign("/login/"))
      .catch((error: unknown) => {
        console.warn("Logout failed; the browser session may still be active.", {
          failureClass: error instanceof Error ? error.name : typeof error,
        });
        setLogoutError("Log out failed. Your session may still be active. Try again.");
      });
  }, []);

  useEffect(() => {
    if (focusRouteHeading(mainRef.current)) return;
    mainRef.current?.focus();
    const observer = new MutationObserver(() => {
      if (focusRouteHeading(mainRef.current)) observer.disconnect();
    });
    if (mainRef.current) observer.observe(mainRef.current, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, [location.pathname]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className={`app-header${hasFullNavigation ? " app-header--full-navigation" : ""}`}>
        <Link
          className={`app-identity ${location.pathname === "/" ? "active" : ""}`}
          to="/"
          aria-label={`Open Dashboard for ${server.name}`}
          aria-current={location.pathname === "/" ? "page" : undefined}
        >
          <img src="/static/web/favicon.png" width="28" height="28" alt="" aria-hidden="true" />
          <strong>{server.name}</strong>
        </Link>

        <div className="app-navigation">
          <nav className="primary-nav" aria-label="Primary navigation">
            {visiblePrimary.map((item) => <AppNavigationLink key={item.to} item={item} pathname={location.pathname} />)}
          </nav>
          <nav className="secondary-nav" aria-label="Administration navigation">
            {visibleSecondary.map((item) => <AppNavigationLink key={item.to} item={item} pathname={location.pathname} secondary />)}
          </nav>
          {overflowItems.length > 0 ? <AppMenuComponent
            className="navigation-overflow-menu"
            trigger={<MaterialIcon name="more_horiz" />}
            triggerLabel="More navigation"
            triggerTitle="More navigation"
            menuLabel="More navigation"
            items={overflowItems}
            active={overflowItems.some((item) => item.active)}
          /> : null}
        </div>

        <AppMenuComponent
          className="account-menu"
          trigger={<><span className="account-menu__username">{user.username}</span><MaterialIcon name="expand_more" className="account-menu__chevron" /></>}
          triggerLabel={`Open account menu for ${user.username}`}
          menuLabel={`Account menu for ${user.username}`}
          items={accountMenuItems(location.pathname, logout)}
          active={accountActive}
        />
      </header>

      {logoutError ? <div className="app-session-feedback"><ErrorPanel>{logoutError}</ErrorPanel></div> : null}

      <div className="app-breadcrumb-slot">
        <BreadcrumbsComponent items={breadcrumbs} />
      </div>

      <main ref={mainRef} id="main-content" className="app-content" tabIndex={-1}>
        <RouteModuleBoundary key={location.pathname}>
          <Suspense fallback={<RouteModuleLoading />}>
            <Outlet context={{ currentUser: user, serverInfo: server, onCurrentUserChange, refreshCurrentUser: onRefreshCurrentUser, refreshServerInfo: onRefreshServerInfo, setBreadcrumbs } satisfies AppOutletContext} />
          </Suspense>
        </RouteModuleBoundary>
      </main>

      <footer className="app-footer">
        <span>Second Pass Library</span>
        <span className="app-footer__server-details">
          <span>{server.version}</span>
        </span>
      </footer>
    </div>
  );
}

function AppNavigationLink({
  item,
  pathname,
  secondary = false,
}: {
  item: NavigationDestination;
  pathname: string;
  secondary?: boolean;
}) {
  const active = navigationDestinationOwnsPath(item.to, pathname);
  return <Link
    className={`app-navigation-link ${secondary ? "app-navigation-link--secondary" : "app-navigation-link--primary"} ${active ? "active" : ""}`}
    to={item.to}
    aria-current={active ? "page" : undefined}
    aria-label={item.label}
    title={item.label}
  >
    <MaterialIcon name={item.icon} />
    <span className="app-navigation-link__label">{item.label}</span>
  </Link>;
}
