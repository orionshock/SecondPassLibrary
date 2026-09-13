import {
  ApiError,
  getGroup,
  listGroupBooks,
  listGroupMembers,
  listShelves,
  type LibraryGroup,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useOutletContext, useParams, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { ErrorPanel } from "../../../components/UiPrimitives";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import {
  canCreateShelfForGroup,
  shelfCreateNavigationStateForGroup,
  shelfNewPath,
} from "../../../shared/shelves/shelfNavigation";
import { tabButtonId, tabPanelId } from "../../../shared/tabs/TabList";
import { groupDetailBreadcrumbFallback } from "../groupsBreadcrumbs";
import { groupEditNavigationState, groupEditPath } from "../groupsBreadcrumbs";
import { canManageGroup } from "../groupMetadataAuthority";
import {
  groupBooksSdkQuery,
  groupDetailPath,
  groupDetailSearchParams,
  groupDetailStateFromSearchParams,
  groupMembersSdkQuery,
  groupShelvesSdkQuery,
  withGroupDetailChange,
} from "../groupsQuery";
import { GroupBooksPageRegion } from "./GroupBooksPageRegion";
import { GroupHeaderPageRegion } from "./GroupHeaderPageRegion";
import { GroupMembersPageRegion } from "./GroupMembersPageRegion";
import { GroupShelvesPageRegion } from "./GroupShelvesPageRegion";
import "../Groups.css";

type GroupLoad =
  | { status: "loading" }
  | { status: "ready"; group: LibraryGroup }
  | { status: "unavailable" }
  | { status: "error"; error: Error };

export function GroupDetailOrchestrator() {
  const { groupId = "" } = useParams<{ groupId: string }>();
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const [searchParameters, setSearchParameters] = useSearchParams();
  const queryKey = searchParameters.toString();
  const queryState = useMemo(
    () => groupDetailStateFromSearchParams(new URLSearchParams(queryKey)),
    [queryKey],
  );
  const canonicalQuery = groupDetailSearchParams(queryState).toString();
  const [searchDraft, setSearchDraft] = useState(queryState.q);
  const [detailRetry, setDetailRetry] = useState(0);
  const [detail, setDetail] = useState<GroupLoad>({ status: "loading" });
  const recoveredQuery = (page: number) => groupDetailSearchParams(withGroupDetailChange(queryState, { page }, false)).toString();
  const booksQuery = groupBooksSdkQuery(queryState);
  const membersQuery = groupMembersSdkQuery(queryState);
  const shelvesQuery = groupShelvesSdkQuery(groupId, queryState);
  const books = useUrlCollectionLifecycle({
    scope: `group:${groupId}:books`,
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listGroupBooks(groupId, { ...booksQuery, page }),
    queryForPage: recoveredQuery,
    locationState: location.state,
    enabled: queryState.tab === "books",
  });
  const members = useUrlCollectionLifecycle({
    scope: `group:${groupId}:members`,
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listGroupMembers(groupId, { ...membersQuery, page }),
    queryForPage: recoveredQuery,
    locationState: location.state,
    enabled: queryState.tab === "members",
  });
  const shelves = useUrlCollectionLifecycle({
    scope: `group:${groupId}:shelves`,
    canonicalQuery,
    page: queryState.page,
    pageSize: queryState.pageSize,
    loadPage: (page) => listShelves({ ...shelvesQuery, page }),
    queryForPage: recoveredQuery,
    locationState: location.state,
    enabled: queryState.tab === "shelves",
  });
  const group = detail.status === "ready" ? detail.group : undefined;
  const breadcrumbs = useMemo(() => groupDetailBreadcrumbFallback(group?.name, group?.isPublicGroup), [group?.isPublicGroup, group?.name]);
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    let active = true;
    setDetail({ status: "loading" });
    getGroup(groupId, { includePreviewBooks: true })
      .then((loadedGroup) => { if (active) setDetail({ status: "ready", group: loadedGroup }); })
      .catch((error: unknown) => {
        if (!active) return;
        setDetail(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [detailRetry, groupId]);

  function changeQuery(
    changes: Parameters<typeof withGroupDetailChange>[1],
    resetPage = true,
    replace = false,
  ) {
    setSearchParameters(groupDetailSearchParams(withGroupDetailChange(queryState, changes, resetPage)), {
      replace,
      state: location.state,
    });
  }

  if (detail.status === "unavailable") {
    return <section className="group-detail-state"><ErrorPanel>Group not found or unavailable.</ErrorPanel></section>;
  }

  const isCurator = Boolean(group && currentUser.groups.some(
    (membership) => membership.id === group.id && membership.isCurator,
  ));
  const canManage = Boolean(group && canManageGroup(currentUser, group, serverInfo.advancedLibraryGroupsEnabled));
  const canCreateGroupShelf = Boolean(group && canCreateShelfForGroup(currentUser, group));
  const currentPath = groupDetailPath(groupId, queryState);

  return <ProductPageShell className="groups-page group-detail-page">
    <GroupHeaderPageRegion
      group={group}
      loading={detail.status === "loading"}
      error={detail.status === "error" ? detail.error : undefined}
      isCurator={isCurator}
      editPath={canManage && group ? groupEditPath(group.id) : undefined}
      editNavigationState={canManage && group
        ? groupEditNavigationState(location.state, group)
        : undefined}
      createShelfPath={canCreateGroupShelf ? shelfNewPath() : undefined}
      createShelfNavigationState={canCreateGroupShelf && group
        ? shelfCreateNavigationStateForGroup(group, currentPath)
        : undefined}
      activeTab={queryState.tab}
      onTabChange={(tab) => changeQuery({ tab })}
      onRetry={() => setDetailRetry((value) => value + 1)}
    />
    {group && queryState.tab === "books" ? <div
      id={tabPanelId("group-detail", "books")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-detail", "books")}
    ><GroupBooksPageRegion
      groupId={group.id}
      groupName={group.name}
      isPublicGroup={group.isPublicGroup}
      groupPath={currentPath}
      page={books.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      search={searchDraft}
      ordering={queryState.ordering}
      loading={books.loading}
      error={books.error === undefined ? undefined : normalizeMutationError(books.error)}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={books.retry}
    /></div> : null}
    {group && queryState.tab === "members" ? <div
      id={tabPanelId("group-detail", "members")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-detail", "members")}
    ><GroupMembersPageRegion
      page={members.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      loading={members.loading}
      error={members.error === undefined ? undefined : normalizeMutationError(members.error)}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={members.retry}
    /></div> : null}
    {group && queryState.tab === "shelves" ? <div
      id={tabPanelId("group-detail", "shelves")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-detail", "shelves")}
    ><GroupShelvesPageRegion
      groupId={group.id}
      groupName={group.name}
      isPublicGroup={group.isPublicGroup}
      groupPath={currentPath}
      page={shelves.page}
      pageNumber={queryState.page}
      pageSize={queryState.pageSize}
      loading={shelves.loading}
      error={shelves.error === undefined ? undefined : normalizeMutationError(shelves.error)}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={shelves.retry}
    /></div> : null}
  </ProductPageShell>;
}
