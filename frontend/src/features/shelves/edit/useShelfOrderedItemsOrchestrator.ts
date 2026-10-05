import {
  addShelfItem, getShelf, listShelfEditorItems, moveShelfItem, removeShelfItem,
  searchGroupBooks, searchLibraryBooks, setShelfItemPosition,
  type ShelfEditorItem, type ShelfSummary,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router";

import { useUrlCollectionLifecycle } from "../../../app/routing/useUrlCollectionLifecycle";
import { normalizeMutationError } from "../../../shared/feedback/mutationState";
import { useAutoDismissMutationMessage } from "../../../shared/feedback/useAutoDismissMutationMessage";
import { confirmUnavailableShelfItemRemoval } from "../shelfLifecycle";
import {
  shelfEditPathWithState, shelfEditSearchParams, shelfEditStateDuringItemMutation,
  shelfEditStateFromSearchParams, withShelfEditPage, type ShelfEditUrlState,
} from "../shelvesQuery";

interface RowMutation {
  pendingId?: string;
  pendingAction?: "move" | "remove";
  error?: Error;
  message?: string;
}

type ItemCommand =
  | { action: "add"; id: string }
  | { action: "remove"; id: string; unavailable: boolean }
  | { action: "move"; id: string; move: "up" | "down" | number };

/** Owns ordered-item settlement; collection loading and page recovery stay shared. */
export function useShelfOrderedItemsOrchestrator({ shelfId, shelf, enabled, disabled, publishItemCount }: {
  shelfId: string;
  shelf?: ShelfSummary;
  enabled: boolean;
  disabled: boolean;
  publishItemCount: (count: number) => void;
}) {
  const location = useLocation();
  const navigate = useNavigate();
  const requested = useMemo(
    () => shelfEditStateFromSearchParams(new URLSearchParams(location.search)),
    [location.search],
  );
  const [itemMutation, setItemMutation] = useState<RowMutation>({});
  const [candidateMutation, setCandidateMutation] = useState<RowMutation>({});
  useAutoDismissMutationMessage(itemMutation, setItemMutation);
  useAutoDismissMutationMessage(candidateMutation, setCandidateMutation);
  // A Shelf lifetime also excludes commands synchronously, before React renders.
  const lifetime = useMemo(() => ({ active: true, pending: false }), [shelfId]);
  useEffect(() => {
    lifetime.active = true;
    setItemMutation({});
    setCandidateMutation({});
    return () => { lifetime.active = false; };
  }, [lifetime]);
  const pending = lifetime.pending;
  const stableState = useRef(requested);
  if (!pending) stableState.current = requested;
  const editState = shelfEditStateDuringItemMutation(requested, stableState.current, pending);
  const canonicalQuery = shelfEditSearchParams(editState).toString();
  const queryForPage = (page: number) => shelfEditSearchParams(withShelfEditPage(editState, { page })).toString();
  function onPageRecovered(page: number) {
    if (lifetime.active && lifetime.pending) {
      stableState.current = withShelfEditPage(stableState.current, { page });
    }
  }
  const itemsLoad = useUrlCollectionLifecycle({
    scope: `shelf:${shelfId}:edit-items`, canonicalQuery,
    page: editState.page, pageSize: editState.pageSize,
    loadPage: (page) => listShelfEditorItems(shelfId, { page, pageSize: editState.pageSize }),
    queryForPage, onPageRecovered, locationState: location.state,
    enabled: enabled && editState.tab === "books",
  });
  const candidatesLoad = useUrlCollectionLifecycle({
    scope: `shelf:${shelfId}:edit-candidates:${editState.q}`, canonicalQuery,
    page: editState.page, pageSize: editState.pageSize,
    loadPage: (page) => {
      const query = {
        q: editState.q, excludeShelfId: shelfId, ordering: "title" as const,
        page, pageSize: editState.pageSize,
      };
      if (shelf?.ownerType !== "group") return searchLibraryBooks(query);
      if (shelf.ownerGroup) return searchGroupBooks(shelf.ownerGroup.id, query);
      return Promise.reject(new Error("Shelf owner group is unavailable."));
    },
    queryForPage, onPageRecovered, locationState: location.state,
    enabled: enabled && editState.tab === "add-books" && Boolean(editState.q),
  });

  useEffect(() => {
    const canonical = shelfEditPathWithState(shelfId, editState);
    if (`${location.pathname}${location.search}` !== canonical) {
      navigate(canonical, { replace: true, state: location.state });
    }
  }, [editState, location.pathname, location.search, location.state, navigate, shelfId]);

  function navigateEditState(next: ShelfEditUrlState, replace = false) {
    if (lifetime.pending) return;
    navigate(shelfEditPathWithState(shelfId, next), { replace, state: location.state });
  }

  async function run(command: ItemCommand) {
    if (!lifetime.active || lifetime.pending || !enabled || disabled) return;
    if (command.action === "remove" && command.unavailable && !confirmUnavailableShelfItemRemoval()) return;
    lifetime.pending = true;
    const setFeedback = command.action === "add" ? setCandidateMutation : setItemMutation;
    setFeedback({ pendingId: command.id, pendingAction: command.action === "add" ? undefined : command.action });
    try {
      if (command.action === "add") await addShelfItem(shelfId, { bookId: command.id });
      else if (command.action === "remove") await removeShelfItem(shelfId, command.id);
      else if (typeof command.move === "number") await setShelfItemPosition(shelfId, command.id, command.move);
      else await moveShelfItem(shelfId, command.id, command.move);
    } catch (error: unknown) {
      if (!lifetime.active) return;
      lifetime.pending = false;
      setFeedback({ error: normalizeMutationError(error) });
      return;
    }
    if (!lifetime.active) return;
    // Never publish the mutation response as order: reload the authoritative page.
    itemsLoad.reload();
    if (command.action === "add") candidatesLoad.reload();
    try {
      const refreshed = await getShelf(shelfId);
      if (!lifetime.active) return;
      publishItemCount(refreshed.itemCount);
      lifetime.pending = false;
      setFeedback({ message: command.action === "add" ? "Book added to shelf."
        : command.action === "move" ? "Shelf order updated."
        : command.unavailable ? "Unavailable item removed." : "Book removed from shelf." });
    } catch {
      if (!lifetime.active) return;
      lifetime.pending = false;
      setFeedback({ error: new Error(command.action === "add" ? "Book added, but the shelf summary could not be refreshed."
        : command.action === "move" ? "Shelf order changed, but the shelf summary could not be refreshed."
        : "Item removed, but the shelf summary could not be refreshed.") });
    }
  }

  return {
    editState, pending, itemMutation, candidateMutation, itemsLoad, candidatesLoad, navigateEditState,
    clearCandidateFeedback: () => { if (!lifetime.pending) setCandidateMutation({}); },
    addItem: (id: string) => run({ action: "add", id }),
    removeItem: (item: ShelfEditorItem) => run({ action: "remove", id: item.id, unavailable: item.unavailable }),
    moveItem: (id: string, move: "up" | "down" | number) => run({ action: "move", id, move }),
  };
}
