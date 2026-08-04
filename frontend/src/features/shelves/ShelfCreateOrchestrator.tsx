import {
  createShelf,
  listAllLibraryGroups,
  type LibraryGroup,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useBlocker, useLocation, useNavigate, useOutletContext } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../shared/feedback/mutationState";
import { ProductPageShellComponent } from "../../shared/layout/ProductPageShellComponent";
import {
  authorizedShelfCreateGroupContext,
  shelfCreateGroupReturnNavigationState,
  shelfEditPath,
} from "../../shared/shelves/shelfNavigation";
import { ShelfDetailsEditPageRegion } from "./regions/ShelfDetailsEditPageRegion";
import {
  createShelfInputFromDraft,
  emptyShelfDraft,
  shelfDraftForGroupOwner,
  shelfDraftFromSummary,
  shelfDraftsEqual,
  validateShelfDraft,
  withShelfOwnerType,
  type ShelfDraft,
} from "./shelfDraft";
import {
  canPresentShelfGroupOwnerChoice,
  localManageableShelfGroups,
  readShelfLifecycleSuccessMessage,
  shelfEditBreadcrumbs,
  shelfEditNavigationState,
  shelfLifecycleNavigationState,
  shelfNewBreadcrumbs,
  shouldLoadAllShelfGroups,
} from "./shelfLifecycle";
import { shelfScopeFromBreadcrumbState, shelfScopeFromSummary, shelfScopePath } from "./shelfScopes";
import "./ShelfLifecycle.css";

interface GroupChoicesLoad {
  loading: boolean;
  items: LibraryGroup[];
  error?: Error;
}

export function ShelfCreateOrchestrator() {
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const groupContext = useMemo(
    () => {
      const candidate = authorizedShelfCreateGroupContext(currentUser, location.state);
      if (!candidate) return undefined;
      return canPresentShelfGroupOwnerChoice(
        candidate,
        serverInfo.advancedLibraryGroupsEnabled,
      )
        ? candidate
        : undefined;
    },
    [currentUser, location.state, serverInfo.advancedLibraryGroupsEnabled],
  );
  const contextGroupChoice = useMemo<LibraryGroup | undefined>(() => (groupContext
    ? {
      id: groupContext.groupId,
      name: groupContext.groupName,
      description: "",
      isPublicGroup: groupContext.isPublicGroup,
    }
    : undefined), [groupContext]);
  const initialLocalGroups = localManageableShelfGroups(currentUser, serverInfo.advancedLibraryGroupsEnabled);
  const initialGroups = contextGroupChoice
    ? withGroupChoice(initialLocalGroups, contextGroupChoice)
    : initialLocalGroups;
  const initialDraft = groupContext
    ? shelfDraftForGroupOwner(groupContext.groupId)
    : { ...emptyShelfDraft };
  const [groups, setGroups] = useState<GroupChoicesLoad>(() => ({
    loading: shouldLoadAllShelfGroups(currentUser, serverInfo.advancedLibraryGroupsEnabled),
    items: initialGroups,
  }));
  const [draft, setDraft] = useState<ShelfDraft>(initialDraft);
  const [baseline, setBaseline] = useState<ShelfDraft>(initialDraft);
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
  const originatingScope = useMemo(
    () => shelfScopeFromBreadcrumbState(location.state) ?? "personal",
    [location.state],
  );
  const breadcrumbs = useMemo(() => shelfNewBreadcrumbs(originatingScope), [originatingScope]);
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
    if (!shouldLoadAllShelfGroups(currentUser, serverInfo.advancedLibraryGroupsEnabled)) {
      const local = localManageableShelfGroups(currentUser, serverInfo.advancedLibraryGroupsEnabled);
      setGroups({ loading: false, items: contextGroupChoice ? withGroupChoice(local, contextGroupChoice) : local });
      return;
    }
    let active = true;
    setGroups({ loading: true, items: contextGroupChoice ? [contextGroupChoice] : [] });
    listAllLibraryGroups()
      .then((items) => { if (active) setGroups({ loading: false, items }); })
      .catch((error: unknown) => {
        if (active) setGroups({
          loading: false,
          items: contextGroupChoice ? [contextGroupChoice] : [],
          error: normalizeMutationError(error),
        });
      });
    return () => { active = false; };
  }, [contextGroupChoice, currentUser, serverInfo.advancedLibraryGroupsEnabled]);

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
        state: groupContext
          ? {
            ...shelfEditNavigationState(location.state, saved),
            shelfLifecycleSuccessMessage: "Shelf saved.",
          }
          : shelfLifecycleNavigationState(
            shelfEditBreadcrumbs(saved.id, saved.name, shelfScopeFromSummary(saved)),
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
    if (groupContext) {
      navigate(groupContext.returnTo, { state: shelfCreateGroupReturnNavigationState(groupContext) });
      return;
    }
    navigate(shelfScopePath(originatingScope), { state: null });
  }

  return <ProductPageShellComponent className="shelf-lifecycle-page" eyebrow="New Shelf" title="Create Shelf">
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
  </ProductPageShellComponent>;
}

function withGroupChoice(groups: readonly LibraryGroup[], group: LibraryGroup): LibraryGroup[] {
  return groups.some(({ id }) => id === group.id) ? [...groups] : [...groups, group];
}
