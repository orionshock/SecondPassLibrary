import {
  ApiError,
  deleteShelf,
  getShelf,
  updateShelf,
  type ShelfSummary,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";

import { usePageBreadcrumbs } from "../../../app/navigation/usePageBreadcrumbs";
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
import { useShelfOrderedItemsOrchestrator } from "./useShelfOrderedItemsOrchestrator";
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
  readShelfLifecycleSuccessMessage,
  shelfDetailNavigationStateFromEdit,
  shelfEditBreadcrumbs,
} from "../shelfLifecycle";
import {
  withShelfEditPage,
  withShelfEditTab,
} from "../shelvesQuery";
import { shelfScopeFromSummary, validBreadcrumbStateForShelf } from "../shelfScopes";
import "../ShelfLifecycle.css";

type ShelfLoad =
  | { status: "loading" }
  | { status: "ready"; shelf: ShelfSummary }
  | { status: "unavailable" }
  | { status: "not-allowed"; shelf: ShelfSummary }
  | { status: "error"; error: Error };

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
  const shelf = load.status === "ready" || load.status === "not-allowed" ? load.shelf : undefined;
  const {
    editState, pending: immediateItemMutationPending, itemMutation, candidateMutation,
    itemsLoad, candidatesLoad, navigateEditState, clearCandidateFeedback, addItem, removeItem, moveItem,
  } = useShelfOrderedItemsOrchestrator({
    shelfId, shelf, enabled: load.status === "ready", disabled: mutation.pending || deleteMutation.pending,
    publishItemCount: (itemCount) => setLoad((current) => current.status === "ready" && current.shelf.id === shelfId
      ? { status: "ready", shelf: { ...current.shelf, itemCount } }
      : current),
  });
  const [searchDraft, setSearchDraft] = useState(editState.q);
  const scope = shelf ? shelfScopeFromSummary(shelf) : "personal";
  const breadcrumbs = useMemo(
    () => shelfEditBreadcrumbs(shelfId, shelf?.name, scope),
    [scope, shelf?.name, shelfId],
  );
  usePageBreadcrumbs(breadcrumbs, false, {
    locationState: shelf ? validBreadcrumbStateForShelf(location.state, shelf) : location.state,
  });

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
        onSearchChange={(value) => { setSearchDraft(value); clearCandidateFeedback(); }}
        onSearch={() => navigateEditState({ ...editState, q: searchDraft.trim(), page: 1 })}
        onAdd={(bookId) => void addItem(bookId)}
        onPageChange={(page) => navigateEditState(withShelfEditPage(editState, { page }))}
        onPageSizeChange={(pageSize) => navigateEditState(withShelfEditPage(editState, { pageSize }))}
        onRetry={candidatesLoad.retry}
      />
    </div> : null}
  </ProductPageShell>;
}
