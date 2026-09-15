import {
  addBookToGroup,
  ApiError,
  deleteGroup,
  getGroup,
  listGroupBooks,
  removeBookFromGroup,
  searchLibraryBooks,
  updateGroup,
  type CompactBook,
  type LibraryGroup,
  type Page,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useOutletContext, useParams } from "react-router";

import type { AppOutletContext } from "../../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { Button, ErrorPanel } from "../../../components/UiPrimitives";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../../shared/feedback/useAutoDismissMutationMessage";
import { useFormSaveLifecycle } from "../../../shared/forms/useFormSaveLifecycle";
import { ProductPageShell } from "../../../shared/layout/ProductPageShell";
import { tabButtonId, tabPanelId } from "../../../shared/tabs/TabList";
import {
  emptyGroupDraft,
  groupDraftFromGroup,
  groupDraftsEqual,
  updateGroupInputFromDraft,
  validateGroupDraft,
  type GroupDraft,
} from "../groupDraft";
import { canDeleteGroup, canMutateGroupBooks, canMutateGroupMembers, groupMetadataAuthority } from "../groupMetadataAuthority";
import {
  groupDetailNavigationStateFromEdit,
  groupDetailPath,
  groupEditBreadcrumbFallback,
  groupEditNavigationState,
  readGroupLifecycleSuccessMessage,
} from "../groupsBreadcrumbs";
import "../Groups.css";
import {
  groupEditQueryDuringImmediateMutation,
  groupEditQueryFromSearchParams,
  groupEditSearchParams,
  groupEditQueryWithPage,
  type GroupEditTab,
} from "../groupsQuery";
import { GroupMetadataFormPageRegion } from "../regions/GroupMetadataFormPageRegion";
import { GroupBookCandidatesPageRegion } from "./GroupBookCandidatesPageRegion";
import { GroupBooksEditPageRegion } from "./GroupBooksEditPageRegion";
import { GroupDangerZonePageRegion } from "./GroupDangerZonePageRegion";
import { GroupEditTabsPageRegion } from "./GroupEditTabsPageRegion";
import { GroupMembersEditOrchestrator } from "./GroupMembersEditOrchestrator";
import { GroupPublicDetailsPageRegion } from "./GroupPublicDetailsPageRegion";
import { confirmGroupBookRemoval } from "./groupBookMutation";
import { confirmGroupDelete } from "./groupDelete";

type GroupLoad =
  | { status: "loading" }
  | { status: "ready"; group: LibraryGroup }
  | { status: "unavailable" }
  | { status: "error"; error: Error };

interface BookPageLoad {
  page?: Page<CompactBook>;
  loading: boolean;
  error?: Error;
}

interface BookMutation {
  pendingBookId?: string;
  error?: Error;
  message?: string;
}

export function GroupEditOrchestrator() {
  const { groupId = "" } = useParams<{ groupId: string }>();
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<GroupLoad>({ status: "loading" });
  const lifecycle = useFormSaveLifecycle({
    initialDraft: { ...emptyGroupDraft },
    draftsEqual: groupDraftsEqual,
    discardMessage: "Discard unsaved Group changes?",
    initialFeedback: readGroupLifecycleSuccessMessage(location.state)
      ? { message: readGroupLifecycleSuccessMessage(location.state) }
      : {},
  });
  const { draft, mutation } = lifecycle;
  const [deleteMutation, setDeleteMutation] = useState<MutationState>(idleMutationState);
  const requestedEditQuery = useMemo(
    () => groupEditQueryFromSearchParams(new URLSearchParams(location.search)),
    [location.search],
  );
  const [bookMutation, setBookMutation] = useState<BookMutation>({});
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidateQuery, setCandidateQuery] = useState("");
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidatePageSize, setCandidatePageSize] = useState(20);
  const [candidatesLoad, setCandidatesLoad] = useState<BookPageLoad>({ loading: false });
  const [candidatesVersion, setCandidatesVersion] = useState(0);
  const [candidateMutation, setCandidateMutation] = useState<BookMutation>({});
  useAutoDismissMutationMessage(bookMutation, setBookMutation);
  useAutoDismissMutationMessage(candidateMutation, setCandidateMutation);
  const [memberMutationPending, setMemberMutationPending] = useState(false);
  const bookMutationPending = Boolean(bookMutation.pendingBookId || candidateMutation.pendingBookId);
  const immediateMutationPending = bookMutationPending || memberMutationPending;
  const stableEditQuery = useRef(requestedEditQuery);
  if (!immediateMutationPending) stableEditQuery.current = requestedEditQuery;
  const editQuery = groupEditQueryDuringImmediateMutation(
    requestedEditQuery,
    stableEditQuery.current,
    immediateMutationPending,
  );
  const activeTab = editQuery.tab;
  const group = load.status === "ready" ? load.group : undefined;
  const metadataAuthority = group ? groupMetadataAuthority(currentUser, group, serverInfo.advancedLibraryGroupsEnabled) : "none";
  const bookMutationAllowed = group ? canMutateGroupBooks(currentUser, group, serverInfo.advancedLibraryGroupsEnabled) : false;
  const memberMutationAllowed = canMutateGroupMembers(currentUser, serverInfo.advancedLibraryGroupsEnabled);
  const deleteAllowed = group ? canDeleteGroup(currentUser, group, serverInfo.advancedLibraryGroupsEnabled) : false;
  const booksLoad = useUrlCollectionLifecycle({
    scope: `group:${groupId}:edit-books`,
    canonicalQuery: editQuery.query,
    page: editQuery.page,
    pageSize: editQuery.pageSize,
    loadPage: (page) => listGroupBooks(groupId, {
      ordering: "title",
      page,
      pageSize: editQuery.pageSize,
    }),
    queryForPage: (page) => groupEditQueryWithPage(editQuery, { page }),
    locationState: location.state,
    enabled: Boolean(group && bookMutationAllowed && activeTab === "books"),
  });
  const breadcrumbs = useMemo(
    () => groupEditBreadcrumbFallback(groupId, group?.name, group?.isPublicGroup),
    [group?.isPublicGroup, group?.name, groupId],
  );
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    const currentQuery = location.search.startsWith("?") ? location.search.slice(1) : location.search;
    if (currentQuery === editQuery.query) return;
    navigate({ pathname: location.pathname, search: editQuery.query }, {
      replace: true,
      state: location.state,
    });
  }, [editQuery.query, location.pathname, location.search, location.state, navigate]);

  useEffect(() => {
    lifecycle.protectNavigation();
    if (!groupId) {
      setLoad({ status: "unavailable" });
      return;
    }
    let active = true;
    setLoad({ status: "loading" });
    getGroup(groupId)
      .then((loadedGroup) => {
        if (!active) return;
        const next = groupDraftFromGroup(loadedGroup);
        setLoad({ status: "ready", group: loadedGroup });
        lifecycle.loadDraft(next);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoad(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [currentUser, groupId, retry]);

  useEffect(() => {
    if (!group || !bookMutationAllowed || activeTab !== "add-books") return;
    if (!candidateQuery) {
      setCandidatesLoad({ loading: false });
      return;
    }
    let active = true;
    setCandidatesLoad((current) => ({ ...current, loading: true, error: undefined }));
    searchLibraryBooks({
      q: candidateQuery,
      excludeGroupId: group.id,
      ordering: "title",
      page: candidatePage,
      pageSize: candidatePageSize,
    }).then((page) => { if (active) setCandidatesLoad({ page, loading: false }); })
      .catch((error: unknown) => {
        if (active) setCandidatesLoad((current) => ({ ...current, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [activeTab, bookMutationAllowed, candidatePage, candidatePageSize, candidateQuery, candidatesVersion, group]);

  function change<K extends keyof GroupDraft>(field: K, value: GroupDraft[K]) {
    lifecycle.changeDraft((current) => ({ ...current, [field]: value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateGroupDraft(draft);
    } catch (error: unknown) {
      lifecycle.setError(normalizeMutationError(error));
      return;
    }
    if (!lifecycle.beginSave()) return;
    try {
      const saved = await updateGroup(groupId, updateGroupInputFromDraft(draft));
      const next = groupDraftFromGroup(saved);
      setLoad({ status: "ready", group: saved });
      lifecycle.saveSucceeded(next, "Group saved.");
      navigate({ pathname: location.pathname, search: location.search }, {
        replace: true,
        state: groupEditNavigationState(location.state, saved),
      });
    } catch (error: unknown) {
      lifecycle.saveFailed(normalizeMutationError(error));
    }
  }

  function cancel() {
    if (!group) return;
    if (!lifecycle.confirmDiscard()) return;
    navigate(groupDetailPath(group.id), {
      state: groupDetailNavigationStateFromEdit(location.state, group),
    });
  }

  function changeTab(tab: GroupEditTab) {
    if (immediateMutationPending) return;
    const parameters = groupEditSearchParams(new URLSearchParams(location.search), tab);
    navigate({ pathname: location.pathname, search: parameters.toString() }, {
      state: location.state,
    });
    setBookMutation({});
    setCandidateMutation({});
  }

  async function removeBook(book: CompactBook) {
    if (!group || !confirmGroupBookRemoval()) return;
    setBookMutation({ pendingBookId: book.id });
    try {
      await removeBookFromGroup(group.id, book.id);
      setBookMutation({ message: "Book removed from group." });
      booksLoad.reload();
      if (candidateQuery) setCandidatesVersion((value) => value + 1);
    } catch (error: unknown) {
      setBookMutation({ error: normalizeMutationError(error) });
    }
  }

  async function addBook(bookId: string) {
    if (!group) return;
    setCandidateMutation({ pendingBookId: bookId });
    try {
      await addBookToGroup(group.id, bookId);
      setCandidateMutation({ message: "Book added to group." });
      booksLoad.reload();
      if (candidatePage > 1 && candidatesLoad.page?.items.length === 1) setCandidatePage(candidatePage - 1);
      else setCandidatesVersion((value) => value + 1);
    } catch (error: unknown) {
      setCandidateMutation({ error: normalizeMutationError(error) });
    }
  }

  async function removeGroup() {
    if (!group || !deleteAllowed || !confirmGroupDelete()) return;
    setDeleteMutation({ pending: true });
    try {
      await deleteGroup(group.id);
      lifecycle.permitNavigation();
      navigate("/groups", { replace: true, state: null });
    } catch (error: unknown) {
      setDeleteMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  if (load.status === "loading") {
    return <section className="group-lifecycle-state" aria-live="polite" aria-busy="true">Loading group...</section>;
  }
  if (load.status === "unavailable") {
    return <section className="group-lifecycle-state"><ErrorPanel>Group not found or unavailable.</ErrorPanel><Link to="/groups">Back to Groups</Link></section>;
  }
  if (load.status === "error") {
    return <section className="group-lifecycle-state"><ErrorPanel>{load.error.message}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></section>;
  }

  if (metadataAuthority === "none" && !bookMutationAllowed && !memberMutationAllowed) {
    return <section className="group-lifecycle-state"><ErrorPanel>This Group is not available for editing.</ErrorPanel><Link to={groupDetailPath(load.group.id)}>Back to Group</Link></section>;
  }

  return <ProductPageShell className="groups-page group-lifecycle-page" eyebrow="Managing Group" title={draft.name || load.group.name}>
    <GroupEditTabsPageRegion activeTab={activeTab} disabled={immediateMutationPending} onTabChange={changeTab} />
    {activeTab === "details" ? <div
      id={tabPanelId("group-edit", "details")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-edit", "details")}
    >
    {metadataAuthority === "none" ? <GroupPublicDetailsPageRegion group={load.group} /> : <GroupMetadataFormPageRegion
        mode="edit"
        draft={draft}
        nameEditable={metadataAuthority === "full"}
        state={mutation}
        onChange={change}
        onSubmit={(event) => void save(event)}
        onCancel={cancel}
        disabled={deleteMutation.pending}
      />}
    {deleteAllowed ? <GroupDangerZonePageRegion
      state={deleteMutation}
      controlsDisabled={mutation.pending || immediateMutationPending}
      onDelete={() => void removeGroup()}
    /> : null}
    </div> : null}
    {activeTab === "books" ? <div
      id={tabPanelId("group-edit", "books")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-edit", "books")}
    >{bookMutationAllowed ? <>
      {bookMutation.message ? <p className="group-edit-section-feedback" aria-live="polite">{bookMutation.message}</p> : null}
      <GroupBooksEditPageRegion
        groupId={load.group.id}
        groupName={load.group.name}
        isPublicGroup={load.group.isPublicGroup}
        page={booksLoad.page}
        pageNumber={editQuery.page}
        pageSize={editQuery.pageSize}
        loading={booksLoad.loading}
        error={bookMutation.error ?? (booksLoad.error === undefined ? undefined : normalizeMutationError(booksLoad.error))}
        pendingBookId={bookMutation.pendingBookId}
        controlsDisabled={mutation.pending || Boolean(candidateMutation.pendingBookId)}
        onRemove={(book) => void removeBook(book)}
        onPageChange={(page) => navigate({ pathname: location.pathname, search: groupEditQueryWithPage(editQuery, { page }) }, { state: location.state })}
        onPageSizeChange={(pageSize) => navigate({ pathname: location.pathname, search: groupEditQueryWithPage(editQuery, { pageSize }) }, { state: location.state })}
        onRetry={() => { setBookMutation({}); booksLoad.retry(); }}
      />
    </> : <section className="group-edit-section-state" aria-label="Books unavailable"><p className="muted">Book curation is not available for this account.</p></section>}</div> : null}
    {activeTab === "add-books" ? <div
      id={tabPanelId("group-edit", "add-books")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-edit", "add-books")}
    >{bookMutationAllowed ? <>
      {candidateMutation.message ? <p className="group-edit-section-feedback" aria-live="polite">{candidateMutation.message}</p> : null}
      <GroupBookCandidatesPageRegion
        groupId={load.group.id}
        groupName={load.group.name}
        isPublicGroup={load.group.isPublicGroup}
        search={candidateSearch}
        page={candidatesLoad.page}
        pageNumber={candidatePage}
        pageSize={candidatePageSize}
        loading={candidatesLoad.loading}
        error={candidateMutation.error ?? candidatesLoad.error}
        pendingBookId={candidateMutation.pendingBookId}
        controlsDisabled={mutation.pending || Boolean(bookMutation.pendingBookId)}
        onSearchChange={(value) => { setCandidateSearch(value); setCandidateMutation({}); }}
        onSearch={() => { setCandidateQuery(candidateSearch.trim()); setCandidatePage(1); setCandidatesLoad({ loading: false }); }}
        onAdd={(bookId) => void addBook(bookId)}
        onPageChange={setCandidatePage}
        onPageSizeChange={(pageSize) => { setCandidatePageSize(pageSize); setCandidatePage(1); }}
        onRetry={() => { setCandidateMutation({}); setCandidatesVersion((value) => value + 1); }}
      />
    </> : <section className="group-edit-section-state" aria-label="Add Books unavailable"><p className="muted">Book curation is not available for this account.</p></section>}</div> : null}
    {activeTab === "members" ? <div
      id={tabPanelId("group-edit", "members")}
      role="tabpanel"
      aria-labelledby={tabButtonId("group-edit", "members")}
    >{memberMutationAllowed
      ? <GroupMembersEditOrchestrator group={load.group} metadataPending={mutation.pending} onMutationPendingChange={setMemberMutationPending} />
      : <section className="group-edit-section-state" aria-label="Members unavailable"><p className="muted">Membership management is not available for this account.</p></section>}</div> : null}
  </ProductPageShell>;
}
