import { listGroups, type LibraryGroup, type Page } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { groupsListBreadcrumbFallback } from "./groupsBreadcrumbs";
import {
  groupsListSdkQuery,
  groupsListSearchParams,
  groupsListStateFromSearchParams,
  withGroupsListChange,
} from "./groupsQuery";
import { GroupsListPageRegion } from "./regions/GroupsListPageRegion";
import "./Groups.css";

interface GroupsLoadState {
  page?: Page<LibraryGroup>;
  loading: boolean;
  error?: Error;
}

export function GroupsListOrchestrator() {
  usePageBreadcrumbs(groupsListBreadcrumbFallback);
  const { currentUser } = useOutletContext<AppOutletContext>();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => groupsListStateFromSearchParams(new URLSearchParams(queryKey)),
    [queryKey],
  );
  const canonicalQuery = groupsListSearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<GroupsLoadState>({ loading: true });
  const recoveredPageKeys = useRef(new Set<string>());

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: null });
  }, [canonicalQuery, queryKey, setSearchParameters]);

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    setLoad((current) => ({ page: current.page, loading: true }));
    const sdkQuery = groupsListSdkQuery(queryState);
    loadPageWithRecovery({
      requestedPage: queryState.page,
      pageSize: queryState.pageSize,
      recoveryKey: `groups:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage: (page) => listGroups({ ...sdkQuery, page }),
      buildRecoveredLocation: (page) => groupsListSearchParams(withGroupsListChange(queryState, { page }, false)).toString(),
      replaceLocation: (location) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(location), { replace: true, state: null });
        return true;
      },
    })
      .then(({ page, recovered }) => {
        if (!active) return;
        if (recovered) return;
        setLoad({ page, loading: false });
      })
      .catch((error: unknown) => {
        if (active) setLoad((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [canonicalQuery, queryKey, queryState.ordering, queryState.page, queryState.pageSize, queryState.q, retry, setSearchParameters]);

  function changeQuery(changes: Parameters<typeof withGroupsListChange>[1], resetPage = true) {
    setSearchParameters(groupsListSearchParams(withGroupsListChange(queryState, changes, resetPage)), { state: null });
  }

  const curatorGroupIds = new Set(
    currentUser.groups.filter(({ isCurator }) => isCurator).map(({ id }) => id),
  );

  return <div className="page-stack groups-page">
    <GroupsListPageRegion
      page={load.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      search={searchDraft}
      ordering={queryState.ordering}
      loading={load.loading}
      error={load.error}
      curatorGroupIds={curatorGroupIds}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setRetry((value) => value + 1)}
    />
  </div>;
}
