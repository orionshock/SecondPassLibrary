import type { CurrentUser, ServerInfo } from "@second-pass/spl-api";
import type { ReactNode } from "react";
import { Navigate, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../layout/AppFrame";

export const unauthorizedRouteFallback = "/";

export function RoleRouteGuardComponent({ canAccess, children }: {
  canAccess: (user: CurrentUser, server: ServerInfo) => boolean;
  children: ReactNode;
}) {
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  return canAccess(currentUser, serverInfo) ? children : <Navigate to={unauthorizedRouteFallback} replace />;
}
