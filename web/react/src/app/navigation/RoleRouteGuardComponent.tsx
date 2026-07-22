import type { CurrentUser } from "@second-pass/spl-api";
import type { ReactNode } from "react";
import { Navigate, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../layout/AppFrame";

export const unauthorizedRouteFallback = "/";

export function RoleRouteGuardComponent({ canAccess, children }: {
  canAccess: (user: CurrentUser) => boolean;
  children: ReactNode;
}) {
  const { currentUser } = useOutletContext<AppOutletContext>();
  return canAccess(currentUser) ? children : <Navigate to={unauthorizedRouteFallback} replace />;
}
