import {
  addShelfItem,
  ApiError,
  createShelf,
  deleteShelf,
  getShelf,
  listAllLibraryGroups,
  listGroupBooks,
  listShelfEditorItems,
  moveShelfItem,
  removeShelfItem,
  searchLibraryBooks,
  updateShelf,
  type CompactBook,
  type LibraryGroup,
  type Page,
  type ShelfEditorItem,
  type ShelfEditorItemsPage,
  type ShelfSummary,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import {
  Link,
  useBlocker,
  useLocation,
  useNavigate,
  useOutletContext,
  useParams,
} from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../components/ui";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../shared/feedback/mutationState";
import {
  createShelfInputFromDraft,
  emptyShelfDraft,
  shelfDraftFromSummary,
  shelfDraftsEqual,
  updateShelfInputFromDraft,
  validateShelfDraft,
  withShelfOwnerType,
  type ShelfDraft,
} from "./shelfDraft";
import {
  confirmShelfDelete,
  confirmUnavailableShelfItemRemoval,
  localManageableShelfGroups,
  readShelfLifecycleSuccessMessage,
  shelfDetailNavigationStateFromEdit,
  shelfDetailPathForId,
  shelfEditBreadcrumbs,
  shelfEditPath,
  shelfLifecycleNavigationState,
  shelfNewBreadcrumbs,
  shouldLoadAllShelfGroups,
  type ShelfLifecycleMode,
} from "./shelfLifecycle";
import { ShelfDetailsEditPageRegion } from "./regions/ShelfDetailsEditPageRegion";
import { ShelfEditAddBooksPageRegion } from "./regions/ShelfEditAddBooksPageRegion";
import { ShelfEditBooksPageRegion } from "./regions/ShelfEditBooksPageRegion";
import { ShelfEditTabsPageRegion } from "./regions/ShelfEditTabsPageRegion";
import {
  shelfEditPathWithState,
  shelfEditSearchParams,
  shelfEditStateFromSearchParams,
  withShelfEditPage,
  withShelfEditTab,
  type ShelfEditUrlState,
} from "./shelvesQuery";
import "./ShelfLifecycle.css";

type ShelfLoad =
  | { status: "loading" }
  | { status: "ready"; shelf?: ShelfSummary }
  | { status: "unavailable" }
  | { status: "not-allowed"; shelf: ShelfSummary }
  | { status: "error"; error: Error };

interface GroupChoicesLoad {
  loading: boolean;
  items: LibraryGroup[];
  error?: Error;
}

interface PageLoad<T> {
  page?: Page<T>;
  loading: boolean;
  error?: Error;
}

interface RowMutation {
  pendingId?: string;
  pendingAction?: "move" | "remove";
  error?: Error;
  message?: string;
}

export function ShelfLifecycleOrchestrator({ mode }: { mode: ShelfLifecycleMode }) {
  const { shelfId = "" } = useParams<{ shelfId: string }>();
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<ShelfLoad>(mode === "new" ? { status: "ready" } : { status: "loading" });
  const [groups, setGroups] = useState<GroupChoicesLoad>(() => ({
    loading: shouldLoadAllShelfGroups(currentUser),
    items: localManageableShelfGroups(currentUser),
  }));
  const [draft, setDraft] = useState<ShelfDraft>({ ...emptyShelfDraft });
  const [baseline, setBaseline] = useState<ShelfDraft>({ ...emptyShelfDraft });
  const [mutation, setMutation] = useState<MutationState>(() => ({
    ...idleMutationState,
    ...(readShelfLifecycleSuccessMessage(location.state)
      ? { message: readShelfLifecycleSuccessMessage(location.state) }
      : {}),
  }));
  const [deleteMutation, setDeleteMutation] = useState<MutationState>(idleMutationState);
  const editState = useMemo(
    () => shelfEditStateFromSearchParams(new URLSearchParams(location.search)),
    [location.search],
  );
  const [searchDraft, setSearchDraft] = useState(editState.q);
  const [itemsLoad, setItemsLoad] = useState<PageLoad<ShelfEditorItem> & { page?: ShelfEditorItemsPage }>({ loading: false });
  const [candidatesLoad, setCandidatesLoad] = useState<PageLoad<CompactBook>>({ loading: false });
  const [itemMutation, setItemMutation] = useState<RowMutation>({});
  const [candidateMutation, setCandidateMutation] = useState<RowMutation>({});
  const [itemsVersion, setItemsVersion] = useState(0);
  const [candidatesVersion, setCandidatesVersion] = useState(0);
  const allowNavigation = useRef(false);
  const shelf = load.status === "ready" || load.status === "not-allowed" ? load.shelf : undefined;
  const dirty = !shelfDraftsEqual(draft, baseline);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname
  ));
  const breadcrumbs = useMemo(
    () => mode === "new" ? shelfNewBreadcrumbs() : shelfEditBreadcrumbs(shelfId, shelf?.name),
    [mode, shelf?.name, shelfId],
  );
  usePageBreadcrumbs(breadcrumbs);

  useEffect(() => {
    if (mode !== "edit" || !shelfId) return;
    const canonical = shelfEditPathWithState(shelfId, editState);
    if (`${location.pathname}${location.search}` !== canonical) {
      navigate(canonical, { replace: true, state: location.state });
    }
  }, [editState, location.pathname, location.search, location.state, mode, navigate, shelfId]);

  useEffect(() => { setSearchDraft(editState.q); }, [editState.q]);

  useEffect(() => {
    const preventUnload = (event: BeforeUnloadEvent) => { if (dirty) event.preventDefault(); };
    window.addEventListener("beforeunload", preventUnload);
    return () => window.removeEventListener("beforeunload", preventUnload);
  }, [dirty]);

  useEffect(() => {
    if (blocker.state !== "blocked") return;
    if (window.confirm("Discard unsaved Shelf changes?")) blocker.proceed();
    else blocker.reset();
  }, [blocker]);

  useEffect(() => {
    if (mode !== "new" || !shouldLoadAllShelfGroups(currentUser)) {
      setGroups({ loading: false, items: localManageableShelfGroups(currentUser) });
      return;
    }
    let active = true;
    setGroups({ loading: true, items: [] });
    listAllLibraryGroups()
      .then((items) => { if (active) setGroups({ loading: false, items }); })
      .catch((error: unknown) => {
        if (active) setGroups({ loading: false, items: [], error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [currentUser, mode]);

  useEffect(() => {
    allowNavigation.current = false;
    if (mode === "new") {
      const empty = { ...emptyShelfDraft };
      setLoad({ status: "ready" });
      setDraft(empty);
      setBaseline(empty);
      return;
    }
    if (!shelfId) {
      setLoad({ status: "unavailable" });
      return;
    }
    let active = true;
    setLoad({ status: "loading" });
    getShelf(shelfId)
      .then((loadedShelf) => {
        if (!active) return;
        const next = shelfDraftFromSummary(loadedShelf);
        setDraft(next);
        setBaseline(next);
        setLoad(loadedShelf.canEdit
          ? { status: "ready", shelf: loadedShelf }
          : { status: "not-allowed", shelf: loadedShelf });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoad(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [mode, retry, shelfId]);

  useEffect(() => {
    if (mode !== "edit" || load.status !== "ready" || editState.tab !== "books") return;
    let active = true;
    setItemsLoad((current) => ({ ...current, loading: true, error: undefined }));
    listShelfEditorItems(shelfId, {
      page: editState.page,
      pageSize: editState.pageSize,
    }).then((page) => {
      if (active) setItemsLoad({ page, loading: false });
    }).catch((error: unknown) => {
      if (active) setItemsLoad((current) => ({ ...current, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [editState.page, editState.pageSize, editState.tab, itemsVersion, load.status, mode, shelfId]);

  useEffect(() => {
    if (mode !== "edit" || load.status !== "ready" || editState.tab !== "add-books") return;
    if (!editState.q) {
      setCandidatesLoad({ loading: false });
      return;
    }
    const currentShelf = shelf;
    if (!currentShelf) return;
    let active = true;
    setCandidatesLoad((current) => ({ ...current, loading: true, error: undefined }));
    const query = {
      q: editState.q,
      excludeShelfId: currentShelf.id,
      ordering: "title" as const,
      page: editState.page,
      pageSize: editState.pageSize,
    };
    const request = currentShelf.ownerType === "group"
      ? currentShelf.ownerGroup
        ? listGroupBooks(currentShelf.ownerGroup.id, query)
        : Promise.reject(new Error("Shelf owner group is unavailable."))
      : searchLibraryBooks(query);
    request.then((page) => {
      if (active) setCandidatesLoad({ page, loading: false });
    }).catch((error: unknown) => {
      if (active) setCandidatesLoad((current) => ({ ...current, loading: false, error: normalizeMutationError(error) }));
    });
    return () => { active = false; };
  }, [
    candidatesVersion,
    editState.page,
    editState.pageSize,
    editState.q,
    editState.tab,
    load.status,
    mode,
    shelf?.id,
    shelf?.ownerGroup?.id,
    shelf?.ownerType,
  ]);

  function change<K extends keyof ShelfDraft>(field: K, value: ShelfDraft[K]) {
    setDraft((current) => ({ ...current, [field]: value }));
    setMutation(idleMutationState);
  }

  function changeOwnerType(ownerType: ShelfDraft["ownerType"]) {
    setDraft((current) => withShelfOwnerType(current, ownerType));
    setMutation(idleMutationState);
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateShelfDraft(
        draft,
        mode === "new" ? groups.items.map(({ id }) => id) : undefined,
      );
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
      return;
    }
    setMutation({ pending: true });
    try {
      const saved = mode === "new"
        ? await createShelf(createShelfInputFromDraft(draft))
        : await updateShelf(shelfId, updateShelfInputFromDraft(draft));
      const next = shelfDraftFromSummary(saved);
      setLoad({ status: "ready", shelf: saved });
      setDraft(next);
      setBaseline(next);
      setMutation({ pending: false, message: "Shelf saved." });
      if (mode === "new") {
        allowNavigation.current = true;
        navigate(shelfEditPath(saved.id), {
          replace: true,
          state: shelfLifecycleNavigationState(
            shelfEditBreadcrumbs(saved.id, saved.name),
            "Shelf saved.",
          ),
        });
      }
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (dirty && !window.confirm("Discard unsaved Shelf changes?")) return;
    allowNavigation.current = true;
    if (mode === "edit" && shelf) {
      navigate(shelfDetailPathForId(shelf.id), {
        state: shelfDetailNavigationStateFromEdit(location.state, shelf),
      });
      return;
    }
    navigate("/shelves", { state: null });
  }

  async function removeShelf() {
    if (!shelf || !confirmShelfDelete()) return;
    setDeleteMutation({ pending: true });
    try {
      await deleteShelf(shelf.id);
      allowNavigation.current = true;
      navigate("/shelves", { replace: true, state: null });
    } catch (error: unknown) {
      setDeleteMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function navigateEditState(next: ShelfEditUrlState, replace = false) {
    navigate(shelfEditPathWithState(shelfId, next), { replace, state: location.state });
  }

  async function refreshShelfItemCount() {
    const refreshed = await getShelf(shelfId);
    setLoad((current) => current.status === "ready" && current.shelf
      ? { status: "ready", shelf: { ...current.shelf, itemCount: refreshed.itemCount } }
      : current);
  }

  async function removeItem(item: ShelfEditorItem) {
    if (item.unavailable && !confirmUnavailableShelfItemRemoval()) return;
    setItemMutation({ pendingId: item.id, pendingAction: "remove" });
    try {
      await removeShelfItem(shelfId, item.id);
      setItemsVersion((value) => value + 1);
    } catch (error: unknown) {
      setItemMutation({ error: normalizeMutationError(error) });
      return;
    }
    try {
      await refreshShelfItemCount();
      setItemMutation({ message: item.unavailable ? "Unavailable item removed." : "Book removed from shelf." });
    } catch {
      setItemMutation({ error: new Error("Item removed, but the shelf summary could not be refreshed.") });
    }
  }

  async function moveItem(itemId: string, move: "up" | "down") {
    setItemMutation({ pendingId: itemId, pendingAction: "move" });
    try {
      await moveShelfItem(shelfId, itemId, move);
      setItemsVersion((value) => value + 1);
    } catch (error: unknown) {
      setItemMutation({ error: normalizeMutationError(error) });
      return;
    }
    try {
      await refreshShelfItemCount();
      setItemMutation({ message: "Shelf order updated." });
    } catch {
      setItemMutation({ error: new Error("Shelf order changed, but the shelf summary could not be refreshed.") });
    }
  }

  async function addItem(bookId: string) {
    setCandidateMutation({ pendingId: bookId });
    try {
      await addShelfItem(shelfId, { bookId });
      setItemsVersion((value) => value + 1);
      setCandidatesVersion((value) => value + 1);
    } catch (error: unknown) {
      setCandidateMutation({ error: normalizeMutationError(error) });
      return;
    }
    try {
      await refreshShelfItemCount();
      setCandidateMutation({ message: "Book added to shelf." });
    } catch {
      setCandidateMutation({ error: new Error("Book added, but the shelf summary could not be refreshed.") });
    }
  }

  if (load.status === "loading") {
    return <section className="shelf-lifecycle-state" aria-live="polite" aria-busy="true">Loading shelf...</section>;
  }
  if (load.status === "unavailable") {
    return <section className="shelf-lifecycle-state"><ErrorPanel>Shelf not found or unavailable.</ErrorPanel><Link to="/shelves">Back to Shelves</Link></section>;
  }
  if (load.status === "not-allowed") {
    return <section className="shelf-lifecycle-state"><ErrorPanel>This shelf is not available for editing.</ErrorPanel><Link to={shelfDetailPathForId(load.shelf.id)}>Back to Shelf</Link></section>;
  }
  if (load.status === "error") {
    return <section className="shelf-lifecycle-state"><ErrorPanel>{load.error.message}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></section>;
  }

  return <div className="page-stack shelf-lifecycle-page">
    <PageHeader
      eyebrow={mode === "new" ? "New Shelf" : "Editing Shelf"}
      title={mode === "new" ? "Create Shelf" : draft.name || shelf?.name || "Shelf"}
    />
    {mode === "edit" ? <ShelfEditTabsPageRegion
      activeTab={editState.tab}
      onTabChange={(tab) => navigateEditState(withShelfEditTab(editState, tab))}
    /> : null}
    {mode === "new" || editState.tab === "details" ? <ShelfDetailsEditPageRegion
      mode={mode}
      shelf={shelf}
      draft={draft}
      groups={groups.items}
      groupsLoading={groups.loading}
      groupsError={groups.error}
      mutation={mutation}
      deleteMutation={deleteMutation}
      itemMutationPending={Boolean(itemMutation.pendingId || candidateMutation.pendingId)}
      onChange={change}
      onOwnerTypeChange={changeOwnerType}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
      onDelete={() => void removeShelf()}
    /> : null}
    {mode === "edit" && shelf && editState.tab === "books" ? <>
      {itemMutation.message ? <p className="shelf-edit-section-feedback" aria-live="polite">{itemMutation.message}</p> : null}
      <ShelfEditBooksPageRegion
        shelfId={shelf.id}
        shelfName={shelf.name}
        page={itemsLoad.page}
        pageNumber={editState.page}
        pageSize={editState.pageSize}
        loading={itemsLoad.loading}
        error={itemMutation.error ?? itemsLoad.error}
        pendingItemId={itemMutation.pendingId}
        pendingAction={itemMutation.pendingAction}
        controlsDisabled={mutation.pending || deleteMutation.pending}
        onMove={(itemId, move) => void moveItem(itemId, move)}
        onRemove={(item) => void removeItem(item)}
        onPageChange={(page) => navigateEditState(withShelfEditPage(editState, { page }))}
        onPageSizeChange={(pageSize) => navigateEditState(withShelfEditPage(editState, { pageSize }))}
        onRetry={() => setItemsVersion((value) => value + 1)}
      />
    </> : null}
    {mode === "edit" && shelf && editState.tab === "add-books" ? <>
      {candidateMutation.message ? <p className="shelf-edit-section-feedback" aria-live="polite">{candidateMutation.message}</p> : null}
      <ShelfEditAddBooksPageRegion
        shelfId={shelf.id}
        shelfName={shelf.name}
        search={searchDraft}
        page={candidatesLoad.page}
        pageNumber={editState.page}
        pageSize={editState.pageSize}
        loading={candidatesLoad.loading}
        error={candidateMutation.error ?? candidatesLoad.error}
        pendingBookId={candidateMutation.pendingId}
        controlsDisabled={mutation.pending || deleteMutation.pending}
        onSearchChange={(value) => { setSearchDraft(value); setCandidateMutation({}); }}
        onSearch={() => navigateEditState({ ...editState, q: searchDraft.trim(), page: 1 })}
        onAdd={(bookId) => void addItem(bookId)}
        onPageChange={(page) => navigateEditState(withShelfEditPage(editState, { page }))}
        onPageSizeChange={(pageSize) => navigateEditState(withShelfEditPage(editState, { pageSize }))}
        onRetry={() => setCandidatesVersion((value) => value + 1)}
      />
    </> : null}
  </div>;
}
