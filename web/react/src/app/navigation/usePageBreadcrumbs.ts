import { useLayoutEffect } from "react";
import { useLocation, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../layout/AppFrame";
import { resolveBreadcrumbTrail, type BreadcrumbItem } from "./breadcrumbs";

export function usePageBreadcrumbs(
  fallback: readonly BreadcrumbItem[],
  suppress = false,
  options?: { locationState: unknown },
): void {
  const location = useLocation();
  const { setBreadcrumbs } = useOutletContext<AppOutletContext>();
  const locationState = options ? options.locationState : location.state;

  useLayoutEffect(() => {
    setBreadcrumbs(location.pathname, resolveBreadcrumbTrail(locationState, fallback, suppress));
    return () => setBreadcrumbs(location.pathname, []);
  }, [fallback, location.pathname, locationState, setBreadcrumbs, suppress]);
}
