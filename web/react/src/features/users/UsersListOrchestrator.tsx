import { listUsers, type ManagedUser, type Page } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useOutletContext, useSearchParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, PageHeader } from "../../components/ui";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { UsersFiltersPageRegion } from "./regions/UsersFiltersPageRegion";
import { UsersListPageRegion } from "./regions/UsersListPageRegion";
import "./Users.css";
import { usersListBreadcrumbFallback } from "./usersBreadcrumbs";
import { usersListSdkQuery, usersListSearchParams, usersListStateFromSearchParams, withUsersListChange } from "./usersListQuery";

interface UsersLoadState {
  page?: Page<ManagedUser>;
  loading: boolean;
  error?: Error;
}

export function UsersListOrchestrator() {
  usePageBreadcrumbs(usersListBreadcrumbFallback);
  const { currentUser } = useOutletContext<AppOutletContext>();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => usersListStateFromSearchParams(new URLSearchParams(queryKey), currentUser.advancedLibraryGroupsEnabled),
    [currentUser.advancedLibraryGroupsEnabled, queryKey],
  );
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [retry, setRetry] = useState(0);
  const [loadState, setLoadState] = useState<UsersLoadState>({ loading: true });

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    let active = true;
    setLoadState((current) => ({ page: current.page, loading: true }));
    listUsers(usersListSdkQuery(queryState))
      .then((page) => { if (active) setLoadState({ page, loading: false }); })
      .catch((error: unknown) => { if (active) setLoadState((current) => ({ page: current.page, loading: false, error: normalizeMutationError(error) })); });
    return () => { active = false; };
  }, [queryState.isActive, queryState.ordering, queryState.page, queryState.pageSize, queryState.q, queryState.role, retry]);

  function changeQuery(changes: Parameters<typeof withUsersListChange>[1], resetPage = true) {
    setSearchParameters(usersListSearchParams(withUsersListChange(queryState, changes, resetPage)));
  }

  return <div className="page-stack users-page">
    <PageHeader title="Users" actions={<Button type="button" disabled title="User creation is coming in a later slice.">Create User</Button>} />
    <UsersFiltersPageRegion
      search={searchDraft}
      role={queryState.role}
      isActive={queryState.isActive}
      ordering={queryState.ordering}
      advancedGroupsEnabled={currentUser.advancedLibraryGroupsEnabled}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onRoleChange={(role) => changeQuery({ role })}
      onStatusChange={(isActive) => changeQuery({ isActive })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
    />
    <UsersListPageRegion
      page={loadState.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      ordering={queryState.ordering}
      advancedGroupsEnabled={currentUser.advancedLibraryGroupsEnabled}
      loading={loadState.loading}
      error={loadState.error}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setRetry((value) => value + 1)}
    />
  </div>;
}
