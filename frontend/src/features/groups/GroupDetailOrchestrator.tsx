import {
  ApiError,
  getGroup,
  listGroupBooks,
  listGroupMembers,
  listShelves,
  type CompactBook,
  type GroupMembership,
  type LibraryGroup,
  type Page,
  type ShelfSummary,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useOutletContext, useParams, useSearchParams } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { loadPageWithRecovery } from "../../app/routing/pageRecovery";
import { ErrorPanel } from "../../components/ui";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import {
  canCreateShelfForGroup,
  shelfCreateNavigationStateForGroup,
  shelfNewPath,
} from "../../shared/shelves/shelfNavigation";
import { tabButtonId, tabPanelId } from "../../shared/tabs/TabList";
import { groupDetailBreadcrumbFallback } from "./groupsBreadcrumbs";
import { groupEditNavigationState, groupEditPath } from "./groupsBreadcrumbs";
import { canManageGroup } from "./groupMetadataAuthority";
import {
  groupBooksSdkQuery,
  groupDetailPath,
  groupDetailSearchParams,
  groupDetailStateFromSearchParams,
  groupMembersSdkQuery,
  groupShelvesSdkQuery,
  withGroupDetailChange,
} from "./groupsQuery";
import { GroupBooksPageRegion } from "./regions/GroupBooksPageRegion";
import { GroupHeaderPageRegion } from "./regions/GroupHeaderPageRegion";
import { GroupMembersPageRegion } from "./regions/GroupMembersPageRegion";
import { GroupShelvesPageRegion } from "./regions/GroupShelvesPageRegion";
import "./Groups.css";

interface PageLoad<Item> {
  page?: Page<Item>;
  loading: boolean;
  error?: Error;
}

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
  const [pageRetry, setPageRetry] = useState(0);
  const [detail, setDetail] = useState<GroupLoad>({ status: "loading" });
  const [books, setBooks] = useState<PageLoad<CompactBook>>({ loading: true });
  const [members, setMembers] = useState<PageLoad<GroupMembership>>({ loading: true });
  const [shelves, setShelves] = useState<PageLoad<ShelfSummary>>({ loading: true });
  const recoveredPageKeys = useRef(new Set<string>());
  const group = detail.status === "ready" ? detail.group : undefined;
  const breadcrumbs = useMemo(() => groupDetailBreadcrumbFallback(group?.name, group?.isPublicGroup), [group?.isPublicGroup, group?.name]);
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => setSearchDraft(queryState.q), [queryState.q]);

  useEffect(() => {
    if (queryKey === canonicalQuery) return;
    setSearchParameters(new URLSearchParams(canonicalQuery), { replace: true, state: location.state });
  }, [canonicalQuery, location.state, queryKey, setSearchParameters]);

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

  useEffect(() => {
    if (queryKey !== canonicalQuery) return;
    let active = true;
    const locationState = location.state;
    const recoverPage = <Item,>(fetchPage: (page: number) => Promise<Page<Item>>) => loadPageWithRecovery({
      requestedPage: queryState.page,
      pageSize: queryState.pageSize,
      recoveryKey: `${groupId}:${queryState.tab}:${canonicalQuery}`,
      recoveredKeys: recoveredPageKeys.current,
      fetchPage,
      buildRecoveredLocation: (page) => groupDetailSearchParams(withGroupDetailChange(queryState, { page }, false)).toString(),
      replaceLocation: (nextLocation) => {
        if (!active) return false;
        setSearchParameters(new URLSearchParams(nextLocation), { replace: true, state: locationState });
        return true;
      },
    });
    if (queryState.tab === "books") setBooks((current) => ({ page: current.page, loading: true }));
    else if (queryState.tab === "members") setMembers((current) => ({ page: current.page, loading: true }));
    else setShelves((current) => ({ page: current.page, loading: true }));

    const request = (() => {
      if (queryState.tab === "books") {
        return recoverPage((page) => listGroupBooks(groupId, { ...groupBooksSdkQuery(queryState), page }));
      }
      if (queryState.tab === "members") {
        return recoverPage((page) => listGroupMembers(groupId, { ...groupMembersSdkQuery(queryState), page }));
      }
      return recoverPage((page) => listShelves({ ...groupShelvesSdkQuery(groupId, queryState), page }));
    })();
    request
      .then(({ page, recovered }) => {
        if (!active) return;
        if (recovered) return;
        if (queryState.tab === "books") setBooks({ page: page as Page<CompactBook>, loading: false });
        else if (queryState.tab === "members") setMembers({ page: page as Page<GroupMembership>, loading: false });
        else setShelves({ page: page as Page<ShelfSummary>, loading: false });
      })
      .catch((error: unknown) => {
        if (!active) return;
        const normalized = normalizeMutationError(error);
        if (queryState.tab === "books") setBooks((current) => ({ page: current.page, loading: false, error: normalized }));
        else if (queryState.tab === "members") setMembers((current) => ({ page: current.page, loading: false, error: normalized }));
        else setShelves((current) => ({ page: current.page, loading: false, error: normalized }));
      });
    return () => { active = false; };
  }, [canonicalQuery, groupId, pageRetry, queryKey, queryState.ordering, queryState.page, queryState.pageSize, queryState.q, queryState.tab]);

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
      error={books.error}
      onSearchChange={setSearchDraft}
      onSearch={() => changeQuery({ q: searchDraft.trim() })}
      onOrderingChange={(ordering) => changeQuery({ ordering })}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setPageRetry((value) => value + 1)}
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
      error={members.error}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setPageRetry((value) => value + 1)}
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
      error={shelves.error}
      onPageChange={(page) => changeQuery({ page }, false)}
      onPageSizeChange={(pageSize) => changeQuery({ pageSize })}
      onRetry={() => setPageRetry((value) => value + 1)}
    /></div> : null}
  </ProductPageShell>;
}
