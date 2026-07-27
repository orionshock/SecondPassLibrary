import {
  canSeeImports,
  canSeeServerSettings,
  canSeeUsers,
  listRecentReadingSessions,
} from "@second-pass/spl-api";
import { useEffect, useState } from "react";
import { useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { DashboardPageRegion, type RecentReadingState } from "./regions/DashboardPageRegion";
import "./Dashboard.css";

export const DASHBOARD_RECENT_READING_LIMIT = 10;

export function DashboardOrchestrator() {
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const [recentReading, setRecentReading] = useState<RecentReadingState>({ status: "loading" });
  const [retry, setRetry] = useState(0);

  useEffect(() => {
    let active = true;
    setRecentReading({ status: "loading" });
    listRecentReadingSessions({ limit: DASHBOARD_RECENT_READING_LIMIT })
      .then((items) => {
        if (active) setRecentReading({ status: "ready", items });
      })
      .catch((error: unknown) => {
        if (active) setRecentReading({ status: "error", error: normalizeMutationError(error) });
      });
    return () => {
      active = false;
    };
  }, [retry]);

  return <DashboardPageRegion
    description={serverInfo.description}
    bannerText={serverInfo.bannerText}
    recentReading={recentReading}
    showGroups={serverInfo.advancedLibraryGroupsEnabled}
    showImports={canSeeImports(currentUser)}
    showUsers={canSeeUsers(currentUser)}
    showServerSettings={canSeeServerSettings(currentUser)}
    onRetryRecentReading={() => setRetry((value) => value + 1)}
  />;
}
