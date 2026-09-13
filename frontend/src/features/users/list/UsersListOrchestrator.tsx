import { listUsers } from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { Link, useOutletContext, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../../app/layout/AppOrchestrator";
import { breadcrumbNavigationState } from "../../../app/navigation/breadcrumbs";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { Button } from "../../../components/UiPrimitives";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { UsersFiltersPageRegion } from "./UsersFiltersPageRegion";
import { UsersListPageRegion } from "./UsersListPageRegion";
import { creatableUserRoles } from "../userCreateRoles";
import "../Users.css";
import { usersCreateBreadcrumbFallback, usersListBreadcrumbFallback } from "../usersBreadcrumbs";
import { usersListSdkQuery, usersListSearchParams, usersListStateFromSearchParams, withUsersListChange } from "./usersListQuery";

export function UsersListOrchestrator() {
  usePageBreadcrumbs(usersListBreadcrumbFallback);
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => usersListStateFromSearchParams(new URLSearchParams(queryKey), serverInfo.advancedLibraryGroupsEnabled, currentUser.isOwner),
    [currentUser.isOwner, queryKey, serverInfo.advancedLibraryGroupsEnabled],
  );
  const canonicalQuery = useMemo(() => {
    const canonical = new URLSearchParams(queryKey);
    if (canonical.has("role") && !queryState.role) canonical.delete("role");
    return canonical.toString();
  }, [queryKey, queryState.role]);
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const sdkQuery = usersListSdkQuery(queryState);
  const loadState = useUrlCollectionLifecycle({
    scope: "users",
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listUsers({ ...sdkQuery, page }),
    queryForPage: (page) => usersListSearchParams(withUsersListChange(queryState, { page }, false)).toString(),
  });
  const canCreateUsers = creatableUserRoles(currentUser).length > 0;

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

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
      error={loadState.error === undefined ? undefined : normalizeMutationError(loadState.error)}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={loadState.retry}
    />
  </ProductPageShell>;
}
