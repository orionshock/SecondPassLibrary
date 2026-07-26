import {
  createShelf,
  listAllLibraryGroups,
  type LibraryGroup,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useBlocker, useLocation, useNavigate, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { PageHeader } from "../../components/ui";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../shared/feedback/mutationState";
import { ShelfDetailsEditPageRegion } from "./regions/ShelfDetailsEditPageRegion";
import {
  createShelfInputFromDraft,
  emptyShelfDraft,
  shelfDraftFromSummary,
  shelfDraftsEqual,
  validateShelfDraft,
  withShelfOwnerType,
  type ShelfDraft,
} from "./shelfDraft";
import {
  localManageableShelfGroups,
  readShelfLifecycleSuccessMessage,
  shelfEditBreadcrumbs,
  shelfEditPath,
  shelfLifecycleNavigationState,
  shelfNewBreadcrumbs,
  shouldLoadAllShelfGroups,
} from "./shelfLifecycle";
import "./ShelfLifecycle.css";

interface GroupChoicesLoad {
  loading: boolean;
  items: LibraryGroup[];
  error?: Error;
}

export function ShelfCreateOrchestrator() {
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
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
  const allowNavigation = useRef(false);
  const dirty = !shelfDraftsEqual(draft, baseline);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname
  ));
  const breadcrumbs = useMemo(() => shelfNewBreadcrumbs(), []);
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
    if (!shouldLoadAllShelfGroups(currentUser)) {
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
  }, [currentUser]);

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
      validateShelfDraft(draft, groups.items.map(({ id }) => id));
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
      return;
    }
    setMutation({ pending: true });
    try {
      const saved = await createShelf(createShelfInputFromDraft(draft));
      const next = shelfDraftFromSummary(saved);
      setDraft(next);
      setBaseline(next);
      setMutation({ pending: false, message: "Shelf saved." });
      allowNavigation.current = true;
      navigate(shelfEditPath(saved.id), {
        replace: true,
        state: shelfLifecycleNavigationState(
          shelfEditBreadcrumbs(saved.id, saved.name),
          "Shelf saved.",
        ),
      });
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (dirty && !window.confirm("Discard unsaved Shelf changes?")) return;
    allowNavigation.current = true;
    navigate("/shelves", { state: null });
  }

  return <div className="page-stack shelf-lifecycle-page">
    <PageHeader eyebrow="New Shelf" title="Create Shelf" />
    <ShelfDetailsEditPageRegion
      mode="new"
      draft={draft}
      groups={groups.items}
      groupsLoading={groups.loading}
      groupsError={groups.error}
      mutation={mutation}
      deleteMutation={idleMutationState}
      itemMutationPending={false}
      onChange={change}
      onOwnerTypeChange={changeOwnerType}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
      onDelete={() => undefined}
    />
  </div>;
}
