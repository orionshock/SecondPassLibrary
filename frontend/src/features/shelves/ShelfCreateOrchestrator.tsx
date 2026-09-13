import {
  createShelf,
  listAllLibraryGroups,
  type LibraryGroup,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useLocation, useNavigate, useOutletContext } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { idleMutationState, normalizeMutationError } from "../../shared/feedback/mutationState";
import { useFormSaveLifecycle } from "../../shared/forms/useFormSaveLifecycle";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
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
  const lifecycle = useFormSaveLifecycle({
    initialDraft,
    draftsEqual: shelfDraftsEqual,
    discardMessage: "Discard unsaved Shelf changes?",
    initialFeedback: readShelfLifecycleSuccessMessage(location.state)
      ? { message: readShelfLifecycleSuccessMessage(location.state) }
      : {},
  });
  const { draft, mutation } = lifecycle;
  const originatingScope = useMemo(
    () => shelfScopeFromBreadcrumbState(location.state) ?? "personal",
    [location.state],
  );
  const breadcrumbs = useMemo(() => shelfNewBreadcrumbs(originatingScope), [originatingScope]);
  usePageBreadcrumbs(breadcrumbs);

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
    lifecycle.changeDraft((current) => ({ ...current, [field]: value }));
  }

  function changeOwnerType(ownerType: ShelfDraft["ownerType"]) {
    lifecycle.changeDraft((current) => withShelfOwnerType(current, ownerType));
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    try {
      validateShelfDraft(draft, groups.items.map(({ id }) => id));
    } catch (error: unknown) {
      lifecycle.setError(normalizeMutationError(error));
      return;
    }
    if (!lifecycle.beginSave()) return;
    try {
      const saved = await createShelf(createShelfInputFromDraft(draft));
      const next = shelfDraftFromSummary(saved);
      lifecycle.saveSucceeded(next, "Shelf saved.");
      lifecycle.permitNavigation();
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
      lifecycle.saveFailed(normalizeMutationError(error));
    }
  }

  function cancel() {
    if (!lifecycle.confirmDiscard()) return;
    if (groupContext) {
      navigate(groupContext.returnTo, { state: shelfCreateGroupReturnNavigationState(groupContext) });
      return;
    }
    navigate(shelfScopePath(originatingScope), { state: null });
  }

  return <ProductPageShell className="shelf-lifecycle-page" eyebrow="New Shelf" title="Create Shelf">
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
  </ProductPageShell>;
}

function withGroupChoice(groups: readonly LibraryGroup[], group: LibraryGroup): LibraryGroup[] {
  return groups.some(({ id }) => id === group.id) ? [...groups] : [...groups, group];
}
