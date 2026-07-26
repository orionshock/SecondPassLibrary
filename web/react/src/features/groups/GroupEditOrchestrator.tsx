import {
  addBookToGroup,
  ApiError,
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
import { Link, useBlocker, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../components/ui";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../shared/feedback/mutationState";
import {
  emptyGroupDraft,
  groupDraftFromGroup,
  groupDraftsEqual,
  updateGroupInputFromDraft,
  validateGroupDraft,
  type GroupDraft,
} from "./groupDraft";
import { confirmGroupBookRemoval } from "./groupBookMutation";
import { canMutateGroupBooks, canMutateGroupMembers, groupMetadataAuthority } from "./groupMetadataAuthority";
import { GroupMembersEditOrchestrator } from "./GroupMembersEditOrchestrator";
import {
  groupDetailNavigationStateFromEdit,
  groupDetailPath,
  groupEditBreadcrumbFallback,
  groupEditNavigationState,
  readGroupLifecycleSuccessMessage,
} from "./groupsBreadcrumbs";
import { GroupMetadataFormPageRegion } from "./regions/GroupMetadataFormPageRegion";
import { GroupBookCandidatesPageRegion } from "./regions/GroupBookCandidatesPageRegion";
import { GroupBooksEditPageRegion } from "./regions/GroupBooksEditPageRegion";
import { GroupEditTabsPageRegion, type GroupEditTab } from "./regions/GroupEditTabsPageRegion";
import "./Groups.css";

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
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<GroupLoad>({ status: "loading" });
  const [draft, setDraft] = useState<GroupDraft>({ ...emptyGroupDraft });
  const [baseline, setBaseline] = useState<GroupDraft>({ ...emptyGroupDraft });
  const [mutation, setMutation] = useState<MutationState>(() => ({
    ...idleMutationState,
    ...(readGroupLifecycleSuccessMessage(location.state)
      ? { message: readGroupLifecycleSuccessMessage(location.state) }
      : {}),
  }));
  const [activeTab, setActiveTab] = useState<GroupEditTab>("details");
  const [booksPage, setBooksPage] = useState(1);
  const [booksPageSize, setBooksPageSize] = useState(20);
  const [booksLoad, setBooksLoad] = useState<BookPageLoad>({ loading: false });
  const [booksVersion, setBooksVersion] = useState(0);
  const [bookMutation, setBookMutation] = useState<BookMutation>({});
  const [candidateSearch, setCandidateSearch] = useState("");
  const [candidateQuery, setCandidateQuery] = useState("");
  const [candidatePage, setCandidatePage] = useState(1);
  const [candidatePageSize, setCandidatePageSize] = useState(20);
  const [candidatesLoad, setCandidatesLoad] = useState<BookPageLoad>({ loading: false });
  const [candidatesVersion, setCandidatesVersion] = useState(0);
  const [candidateMutation, setCandidateMutation] = useState<BookMutation>({});
  const allowNavigation = useRef(false);
  const group = load.status === "ready" ? load.group : undefined;
  const dirty = !groupDraftsEqual(draft, baseline);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname
  ));
  const breadcrumbs = useMemo(
    () => groupEditBreadcrumbFallback(groupId, group?.name),
    [group?.name, groupId],
  );
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    const preventUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [dirty]);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("Discard unsaved Group changes?")) blocker.proceed();
    else blocker.reset();
  }, [blocker]);

  useEffect(() => {
    allowNavigation.current = false;
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
        setDraft(next);
        setBaseline(next);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoad(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [groupId, retry]);

  const metadataAuthority = group ? groupMetadataAuthority(currentUser, group) : "none";
  const bookMutationAllowed = group ? canMutateGroupBooks(currentUser, group) : false;
  const memberMutationAllowed = canMutateGroupMembers(currentUser);

  useEffect(() => {
    if (!group || !bookMutationAllowed || activeTab !== "books") return;
    let active = true;
    setBooksLoad((current) => ({ ...current, loading: true, error: undefined }));
    listGroupBooks(group.id, { ordering: "title", page: booksPage, pageSize: booksPageSize })
      .then((page) => { if (active) setBooksLoad({ page, loading: false }); })
      .catch((error: unknown) => {
        if (active) setBooksLoad((current) => ({ ...current, loading: false, error: normalizeMutationError(error) }));
      });
    return () => { active = false; };
  }, [activeTab, bookMutationAllowed, booksPage, booksPageSize, booksVersion, group]);

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
    setDraft((current) => ({ ...current, [field]: value }));
    setMutation(idleMutationState);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateGroupDraft(draft);
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
      return;
    }
    setMutation({ pending: true });
    try {
      const saved = await updateGroup(groupId, updateGroupInputFromDraft(draft));
      const next = groupDraftFromGroup(saved);
      setLoad({ status: "ready", group: saved });
      setDraft(next);
      setBaseline(next);
      setMutation({ pending: false, message: "Group saved." });
      navigate(location.pathname, {
        replace: true,
        state: groupEditNavigationState(location.state, saved),
      });
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (!group) return;
    if (dirty && !window.confirm("Discard unsaved Group changes?")) return;
    allowNavigation.current = true;
    navigate(groupDetailPath(group.id), {
      state: groupDetailNavigationStateFromEdit(location.state, group),
    });
  }

  function changeTab(tab: GroupEditTab) {
    setActiveTab(tab);
    setBookMutation({});
    setCandidateMutation({});
  }

  async function removeBook(book: CompactBook) {
    if (!group || !confirmGroupBookRemoval()) return;
    setBookMutation({ pendingBookId: book.id });
    try {
      await removeBookFromGroup(group.id, book.id);
      setBookMutation({ message: "Book removed from group." });
      if (booksPage > 1 && booksLoad.page?.items.length === 1) setBooksPage(booksPage - 1);
      else setBooksVersion((value) => value + 1);
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
      setBooksVersion((value) => value + 1);
      if (candidatePage > 1 && candidatesLoad.page?.items.length === 1) setCandidatePage(candidatePage - 1);
      else setCandidatesVersion((value) => value + 1);
    } catch (error: unknown) {
      setCandidateMutation({ error: normalizeMutationError(error) });
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

  return <div className="page-stack groups-page group-lifecycle-page">
    <PageHeader eyebrow="Editing Group" title={draft.name || load.group.name} />
    <GroupEditTabsPageRegion activeTab={activeTab} canMutateBooks={bookMutationAllowed} canMutateMembers={memberMutationAllowed} onTabChange={changeTab} />
    {activeTab === "details" && metadataAuthority === "none"
      ? <section className="group-edit-section-state"><ErrorPanel>Group metadata is not editable here.</ErrorPanel></section>
      : null}
    {activeTab === "details" && metadataAuthority !== "none" ? <GroupMetadataFormPageRegion
        mode="edit"
        draft={draft}
        nameEditable={metadataAuthority === "full"}
        state={mutation}
        onChange={change}
        onSubmit={(event) => void save(event)}
        onCancel={cancel}
      /> : null}
    {activeTab === "books" && bookMutationAllowed ? <>
      {bookMutation.message ? <p className="group-edit-section-feedback" aria-live="polite">{bookMutation.message}</p> : null}
      <GroupBooksEditPageRegion
        groupId={load.group.id}
        groupName={load.group.name}
        page={booksLoad.page}
        pageNumber={booksPage}
        pageSize={booksPageSize}
        loading={booksLoad.loading}
        error={bookMutation.error ?? booksLoad.error}
        pendingBookId={bookMutation.pendingBookId}
        controlsDisabled={mutation.pending || Boolean(candidateMutation.pendingBookId)}
        onRemove={(book) => void removeBook(book)}
        onPageChange={setBooksPage}
        onPageSizeChange={(pageSize) => { setBooksPageSize(pageSize); setBooksPage(1); }}
        onRetry={() => { setBookMutation({}); setBooksVersion((value) => value + 1); }}
      />
    </> : null}
    {activeTab === "add-books" && bookMutationAllowed ? <>
      {candidateMutation.message ? <p className="group-edit-section-feedback" aria-live="polite">{candidateMutation.message}</p> : null}
      <GroupBookCandidatesPageRegion
        groupId={load.group.id}
        groupName={load.group.name}
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
    </> : null}
    {activeTab === "members" && memberMutationAllowed
      ? <GroupMembersEditOrchestrator group={load.group} metadataPending={mutation.pending} />
      : null}
  </div>;
}
