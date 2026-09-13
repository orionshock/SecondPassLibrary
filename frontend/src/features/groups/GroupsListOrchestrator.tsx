import { listGroups } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../app/routing/useUrlCollectionLifecycle";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import { canCreateGroupMetadata } from "./groupMetadataAuthority";
import { groupNewBreadcrumbs, groupsListBreadcrumbFallback } from "./groupsBreadcrumbs";
import {
  groupsListSdkQuery,
  groupsListSearchParams,
  groupsListStateFromSearchParams,
  withGroupsListChange,
} from "./groupsQuery";
import { GroupsListPageRegion } from "./regions/GroupsListPageRegion";
import "./Groups.css";

export function GroupsListOrchestrator() {
  usePageBreadcrumbs(groupsListBreadcrumbFallback);
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => groupsListStateFromSearchParams(new URLSearchParams(queryKey)),
    [queryKey],
  );
  const canonicalQuery = groupsListSearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const sdkQuery = groupsListSdkQuery(queryState);
  const load = useUrlCollectionLifecycle({
    scope: "groups",
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listGroups({ ...sdkQuery, page }),
    queryForPage: (page) => groupsListSearchParams(withGroupsListChange(queryState, { page }, false)).toString(),
  });

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  function changeQuery(changes: Parameters<typeof withGroupsListChange>[1], resetPage = true) {
    setSearchParameters(groupsListSearchParams(withGroupsListChange(queryState, changes, resetPage)), { state: null });
  }

  const curatorGroupIds = new Set(
    currentUser.groups.filter(({ isCurator }) => isCurator).map(({ id }) => id),
  );

  return <ProductPageShell className="groups-page">
    <GroupsListPageRegion
      page={load.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      search={searchDraft}
      ordering={queryState.ordering}
      loading={load.loading}
      error={load.error === undefined ? undefined : normalizeMutationError(load.error)}
      curatorGroupIds={curatorGroupIds}
      canCreate={canCreateGroupMetadata(currentUser, serverInfo.advancedLibraryGroupsEnabled)}
      newGroupNavigationState={breadcrumbNavigationState(groupNewBreadcrumbs())}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={load.retry}
    />
  </ProductPageShell>;
}
