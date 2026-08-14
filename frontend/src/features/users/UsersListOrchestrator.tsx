import { listUsers, type ManagedUser, type Page } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { breadcrumbNavigationState } from "../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button } from "../../components/ui";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import { UsersFiltersPageRegion } from "./regions/UsersFiltersPageRegion";
import { UsersListPageRegion } from "./regions/UsersListPageRegion";
import { creatableUserRoles } from "./userCreateRoles";
import "./Users.css";
import { usersCreateBreadcrumbFallback, usersListBreadcrumbFallback } from "./usersBreadcrumbs";
import { usersListSdkQuery, usersListSearchParams, usersListStateFromSearchParams, withUsersListChange } from "./usersListQuery";

interface UsersLoadState {
  page?: Page<ManagedUser>;
  loading: boolean;
  error?: Error;
}

export function UsersListOrchestrator() {
  usePageBreadcrumbs(usersListBreadcrumbFallback);
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => usersListStateFromSearchParams(new URLSearchParams(queryKey), serverInfo.advancedLibraryGroupsEnabled, currentUser.isOwner),
    [currentUser.isOwner, queryKey, serverInfo.advancedLibraryGroupsEnabled],
  );
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [retry, setRetry] = useState(0);
  const [loadState, setLoadState] = useState<UsersLoadState>({ loading: true });
  const canCreateUsers = creatableUserRoles(currentUser).length > 0;

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    if (!searchParameters.has("role") || queryState.role) return;
    const normalized = new URLSearchParams(searchParameters);
    normalized.delete("role");
    setSearchParameters(normalized, { replace: true });
  }, [queryState.role, searchParameters, setSearchParameters]);

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

  return <ProductPageShell className="users-page" title="Users" actions={canCreateUsers
      ? <Link className="button" to="/users/new" state={breadcrumbNavigationState(usersCreateBreadcrumbFallback)}>Create User</Link>
      : <Button type="button" disabled>Create User</Button>}>
    <UsersFiltersPageRegion
      search={searchDraft}
      role={queryState.role}
      isActive={queryState.isActive}
      advancedGroupsEnabled={serverInfo.advancedLibraryGroupsEnabled}
      operatorIsOwner={currentUser.isOwner}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onRoleChange={(role) => changeQuery({ role })}
      onStatusChange={(isActive) => changeQuery({ isActive })}
    />
    <UsersListPageRegion
      page={loadState.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      ordering={queryState.ordering}
      advancedGroupsEnabled={serverInfo.advancedLibraryGroupsEnabled}
      loading={loadState.loading}
      error={loadState.error}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setRetry((value) => value + 1)}
    />
  </ProductPageShell>;
}
