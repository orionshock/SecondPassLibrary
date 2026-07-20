import { useLayoutEffect } from "react";
import { useLocation, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../layout/AppFrame";
import { resolveBreadcrumbTrail, type BreadcrumbItem } from "./breadcrumbs";

export function usePageBreadcrumbs(fallback: readonly BreadcrumbItem[], suppress = false): void {
  const location = useLocation();
  const { setBreadcrumbs } = useOutletContext<AppOutletContext>();

  useLayoutEffect(() => {
    setBreadcrumbs(location.pathname, resolveBreadcrumbTrail(location.state, fallback, suppress));
    return () => setBreadcrumbs(location.pathname, []);
  }, [fallback, location.pathname, location.state, setBreadcrumbs, suppress]);
}
