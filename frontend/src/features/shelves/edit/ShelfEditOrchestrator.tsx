import {
  addShelfItem,
  ApiError,
  deleteShelf,
  getShelf,
  searchGroupBooks,
  listShelfEditorItems,
  moveShelfItem,
  removeShelfItem,
  searchLibraryBooks,
  setShelfItemPosition,
  updateShelf,
  type ShelfEditorItem,
  type ShelfSummary,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

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
import { shelfDetailPathForId } from "../../../shared/shelves/shelfNavigation";
import { tabButtonId, tabPanelId } from "../../../shared/tabs/TabList";
import { ShelfDetailsEditPageRegion } from "../regions/ShelfDetailsEditPageRegion";
import { ShelfEditAddBooksPageRegion } from "./ShelfEditAddBooksPageRegion";
import { ShelfEditBooksPageRegion } from "./ShelfEditBooksPageRegion";
import { ShelfEditTabsPageRegion } from "./ShelfEditTabsPageRegion";
import {
  emptyShelfDraft,
  shelfDraftFromSummary,
  shelfDraftsEqual,
  updateShelfInputFromDraft,
  validateShelfDraft,
  type ShelfDraft,
} from "../shelfDraft";
import {
  confirmShelfDelete,
  confirmUnavailableShelfItemRemoval,
  readShelfLifecycleSuccessMessage,
  shelfDetailNavigationStateFromEdit,
  shelfEditBreadcrumbs,
} from "../shelfLifecycle";
import {
  shelfEditPathWithState,
  shelfEditSearchParams,
  shelfEditStateDuringItemMutation,
  shelfEditStateFromSearchParams,
  withShelfEditPage,
  withShelfEditTab,
  type ShelfEditUrlState,
} from "../shelvesQuery";
import { shelfScopeFromSummary, validBreadcrumbStateForShelf } from "../shelfScopes";
import "../ShelfLifecycle.css";

type ShelfLoad =
  | { status: "loading" }
  | { status: "ready"; shelf: ShelfSummary }
  | { status: "unavailable" }
  | { status: "not-allowed"; shelf: ShelfSummary }
  | { status: "error"; error: Error };

interface RowMutation {
  pendingId?: string;
  pendingAction?: "move" | "remove";
  error?: Error;
  message?: string;
}

export function ShelfEditOrchestrator() {
  const { shelfId = "" } = useParams<{ shelfId: string }>();
  const location = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<ShelfLoad>({ status: "loading" });
  const lifecycle = useFormSaveLifecycle({
    initialDraft: { ...emptyShelfDraft },
    draftsEqual: shelfDraftsEqual,
    discardMessage: "Discard unsaved Shelf changes?",
    initialFeedback: readShelfLifecycleSuccessMessage(location.state)
      ? { message: readShelfLifecycleSuccessMessage(location.state) }
      : {},
  });
  const { draft, mutation } = lifecycle;
  const [deleteMutation, setDeleteMutation] = useState<MutationState>(idleMutationState);
  const requestedEditState = useMemo(
    () => shelfEditStateFromSearchParams(new URLSearchParams(location.search)),
    [location.search],
  );
  const [searchDraft, setSearchDraft] = useState(requestedEditState.q);
  const [itemMutation, setItemMutation] = useState<RowMutation>({});
  const [candidateMutation, setCandidateMutation] = useState<RowMutation>({});
  useAutoDismissMutationMessage(itemMutation, setItemMutation);
  useAutoDismissMutationMessage(candidateMutation, setCandidateMutation);
  const immediateItemMutationPending = Boolean(itemMutation.pendingId || candidateMutation.pendingId);
  const stableEditState = useRef(requestedEditState);
  if (!immediateItemMutationPending) stableEditState.current = requestedEditState;
  const editState = shelfEditStateDuringItemMutation(
    requestedEditState,
    stableEditState.current,
    immediateItemMutationPending,
  );
  const shelf = load.status === "ready" || load.status === "not-allowed" ? load.shelf : undefined;
  const canonicalQuery = shelfEditSearchParams(editState).toString();
  const queryForPage = (page: number) => shelfEditSearchParams(
    withShelfEditPage(editState, { page }),
  ).toString();
  const itemsLoad = useUrlCollectionLifecycle({
    scope: `shelf:${shelfId}:edit-items`,
    canonicalQuery,
    page: editState.page,
    pageSize: editState.pageSize,
    loadPage: (page) => listShelfEditorItems(shelfId, {
      page,
      pageSize: editState.pageSize,
    }),
    queryForPage,
    locationState: location.state,
    enabled: load.status === "ready" && editState.tab === "books",
  });
  const candidatesLoad = useUrlCollectionLifecycle({
    scope: `shelf:${shelfId}:edit-candidates:${editState.q}`,
    canonicalQuery,
    page: editState.page,
    pageSize: editState.pageSize,
    loadPage: (page) => {
      const query = {
        q: editState.q,
        excludeShelfId: shelfId,
        ordering: "title" as const,
        page,
        pageSize: editState.pageSize,
      };
      if (shelf?.ownerType !== "group") return searchLibraryBooks(query);
      if (shelf.ownerGroup) return searchGroupBooks(shelf.ownerGroup.id, query);
      return Promise.reject(new Error("Shelf owner group is unavailable."));
    },
    queryForPage,
    locationState: location.state,
    enabled: load.status === "ready" && editState.tab === "add-books" && Boolean(editState.q),
  });
  const scope = shelf ? shelfScopeFromSummary(shelf) : "personal";
  const breadcrumbs = useMemo(
    () => shelfEditBreadcrumbs(shelfId, shelf?.name, scope),
    [scope, shelf?.name, shelfId],
  );
  usePageBreadcrumbs(breadcrumbs, false, {
    locationState: shelf ? validBreadcrumbStateForShelf(location.state, shelf) : location.state,
  });

  useEffect(() => {
    const canonical = shelfEditPathWithState(shelfId, editState);
    if (`${location.pathname}${location.search}` !== canonical) {
      navigate(canonical, { replace: true, state: location.state });
    }
  }, [editState, location.pathname, location.search, location.state, navigate, shelfId]);

  useEffect(() => { setSearchDraft(editState.q); }, [editState.q]);

  useEffect(() => {
    lifecycle.protectNavigation();
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
        lifecycle.loadDraft(next);
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
  }, [retry, shelfId]);

  function change<K extends keyof ShelfDraft>(field: K, value: ShelfDraft[K]) {
    lifecycle.changeDraft((current) => ({ ...current, [field]: value }));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateShelfDraft(draft);
    } catch (error: unknown) {
      lifecycle.setError(normalizeMutationError(error));
      return;
    }
    if (!lifecycle.beginSave()) return;
    try {
      const saved = await updateShelf(shelfId, updateShelfInputFromDraft(draft));
      const next = shelfDraftFromSummary(saved);
      setLoad({ status: "ready", shelf: saved });
      lifecycle.saveSucceeded(next, "Shelf saved.");
    } catch (error: unknown) {
      lifecycle.saveFailed(normalizeMutationError(error));
    }
  }

  function cancel() {
    if (!lifecycle.confirmDiscard()) return;
    if (shelf) {
      navigate(shelfDetailPathForId(shelf.id), {
        state: shelfDetailNavigationStateFromEdit(location.state, shelf),
      });
    }
  }

  async function removeShelf() {
    if (!shelf || !confirmShelfDelete()) return;
    setDeleteMutation({ pending: true });
    try {
      await deleteShelf(shelf.id);
      lifecycle.permitNavigation();
      navigate("/shelves", { replace: true, state: null });
    } catch (error: unknown) {
      setDeleteMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function navigateEditState(next: ShelfEditUrlState, replace = false) {
    if (immediateItemMutationPending) return;
    navigate(shelfEditPathWithState(shelfId, next), { replace, state: location.state });
  }

  async function refreshShelfItemCount() {
    const refreshed = await getShelf(shelfId);
    setLoad((current) => current.status === "ready"
      ? { status: "ready", shelf: { ...current.shelf, itemCount: refreshed.itemCount } }
      : current);
  }

  async function removeItem(item: ShelfEditorItem) {
    if (item.unavailable && !confirmUnavailableShelfItemRemoval()) return;
    setItemMutation({ pendingId: item.id, pendingAction: "remove" });
    try {
      await removeShelfItem(shelfId, item.id);
      itemsLoad.reload();
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

  async function moveItem(itemId: string, move: "up" | "down" | number) {
    setItemMutation({ pendingId: itemId, pendingAction: "move" });
    try {
      if (typeof move === "number") {
        await setShelfItemPosition(shelfId, itemId, move);
      } else {
        await moveShelfItem(shelfId, itemId, move);
      }
      itemsLoad.reload();
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
      itemsLoad.reload();
      candidatesLoad.reload();
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
  const editableShelf = load.shelf;

  return <ProductPageShell className="shelf-lifecycle-page" eyebrow="Editing Shelf" title={draft.name || editableShelf.name || "Shelf"}>
    <ShelfEditTabsPageRegion
      activeTab={editState.tab}
      disabled={immediateItemMutationPending}
      onTabChange={(tab) => navigateEditState(withShelfEditTab(editState, tab))}
    />
    {editState.tab === "details" ? <div
      id={tabPanelId("shelf-edit", "details")}
      role="tabpanel"
      aria-labelledby={tabButtonId("shelf-edit", "details")}
    ><ShelfDetailsEditPageRegion
      mode="edit"
      shelf={editableShelf}
      draft={draft}
      groups={[]}
      groupsLoading={false}
      mutation={mutation}
      deleteMutation={deleteMutation}
      itemMutationPending={immediateItemMutationPending}
      onChange={change}
      onOwnerTypeChange={() => undefined}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
      onDelete={() => void removeShelf()}
    /></div> : null}
    {editState.tab === "books" ? <div
      id={tabPanelId("shelf-edit", "books")}
      role="tabpanel"
      aria-labelledby={tabButtonId("shelf-edit", "books")}
    >
      {itemMutation.message ? <p className="shelf-edit-section-feedback" aria-live="polite">{itemMutation.message}</p> : null}
      <ShelfEditBooksPageRegion
        shelfId={editableShelf.id}
        shelfName={editableShelf.name}
        scope={scope}
        page={itemsLoad.page}
        pageNumber={editState.page}
        pageSize={editState.pageSize}
        loading={itemsLoad.loading}
        error={itemMutation.error ?? (itemsLoad.error === undefined ? undefined : normalizeMutationError(itemsLoad.error))}
        pendingItemId={itemMutation.pendingId}
        pendingAction={itemMutation.pendingAction}
        controlsDisabled={mutation.pending || deleteMutation.pending}
        onMove={(itemId, move) => void moveItem(itemId, move)}
        onMoveTo={(itemId, position) => void moveItem(itemId, position)}
        onRemove={(item) => void removeItem(item)}
        onPageChange={(page) => navigateEditState(withShelfEditPage(editState, { page }))}
        onPageSizeChange={(pageSize) => navigateEditState(withShelfEditPage(editState, { pageSize }))}
        onRetry={itemsLoad.retry}
      />
    </div> : null}
    {editState.tab === "add-books" ? <div
      id={tabPanelId("shelf-edit", "add-books")}
      role="tabpanel"
      aria-labelledby={tabButtonId("shelf-edit", "add-books")}
    >
      {candidateMutation.message ? <p className="shelf-edit-section-feedback" aria-live="polite">{candidateMutation.message}</p> : null}
      <ShelfEditAddBooksPageRegion
        shelfId={editableShelf.id}
        shelfName={editableShelf.name}
        scope={scope}
        search={searchDraft}
        page={editState.q ? candidatesLoad.page : undefined}
        pageNumber={editState.page}
        pageSize={editState.pageSize}
        loading={Boolean(editState.q) && candidatesLoad.loading}
        error={candidateMutation.error ?? (candidatesLoad.error === undefined ? undefined : normalizeMutationError(candidatesLoad.error))}
        pendingBookId={candidateMutation.pendingId}
        controlsDisabled={mutation.pending || deleteMutation.pending}
        onSearchChange={(value) => { setSearchDraft(value); setCandidateMutation({}); }}
        onSearch={() => navigateEditState({ ...editState, q: searchDraft.trim(), page: 1 })}
        onAdd={(bookId) => void addItem(bookId)}
        onPageChange={(page) => navigateEditState(withShelfEditPage(editState, { page }))}
        onPageSizeChange={(pageSize) => navigateEditState(withShelfEditPage(editState, { pageSize }))}
        onRetry={candidatesLoad.retry}
      />
    </div> : null}
  </ProductPageShell>;
}
