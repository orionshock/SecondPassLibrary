import {
  ApiError,
  createShelf,
  deleteShelf,
  getShelf,
  listAllLibraryGroups,
  updateShelf,
  type LibraryGroup,
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
    <ShelfDetailsEditPageRegion
      mode={mode}
      shelf={shelf}
      draft={draft}
      groups={groups.items}
      groupsLoading={groups.loading}
      groupsError={groups.error}
      mutation={mutation}
      deleteMutation={deleteMutation}
      onChange={change}
      onOwnerTypeChange={changeOwnerType}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
      onDelete={() => void removeShelf()}
    />
  </div>;
}
