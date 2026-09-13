import { createGroup } from "@second-pass/spl-api";
import { useMemo, type FormEvent } from "react";
import { useLocation, useNavigate, useOutletContext } from "react-router";

import type { AppOutletContext } from "../../app/layout/AppOrchestrator";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel } from "../../components/UiPrimitives";
import { normalizeMutationError } from "../../shared/feedback/mutationState";
import { useFormSaveLifecycle } from "../../shared/forms/useFormSaveLifecycle";
import { ProductPageShell } from "../../shared/layout/ProductPageShell";
import {
  createGroupInputFromDraft,
  emptyGroupDraft,
  groupDraftFromGroup,
  groupDraftsEqual,
  validateGroupDraft,
  type GroupDraft,
} from "./groupDraft";
import { canCreateGroupMetadata } from "./groupMetadataAuthority";
import {
  groupEditNavigationState,
  groupEditPath,
  groupNewBreadcrumbs,
} from "./groupsBreadcrumbs";
import { GroupMetadataFormPageRegion } from "./regions/GroupMetadataFormPageRegion";
import "./Groups.css";

export function GroupCreateOrchestrator() {
  const { currentUser, serverInfo } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const lifecycle = useFormSaveLifecycle({
    initialDraft: { ...emptyGroupDraft },
    draftsEqual: groupDraftsEqual,
    discardMessage: "Discard unsaved Group changes?",
  });
  const { draft, mutation } = lifecycle;
  const breadcrumbs = useMemo(() => groupNewBreadcrumbs(), []);
  usePageBreadcrumbs(breadcrumbs);

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
      const saved = await createGroup(createGroupInputFromDraft(draft));
      const next = groupDraftFromGroup(saved);
      lifecycle.saveSucceeded(next);
      lifecycle.permitNavigation();
      navigate(groupEditPath(saved.id), {
        replace: true,
        state: groupEditNavigationState(location.state, saved, "Group created."),
      });
    } catch (error: unknown) {
      lifecycle.saveFailed(normalizeMutationError(error));
    }
  }

  function cancel() {
    if (!lifecycle.confirmDiscard()) return;
    navigate("/groups", { state: null });
  }

  if (!canCreateGroupMetadata(currentUser, serverInfo.advancedLibraryGroupsEnabled)) {
    return <section className="group-lifecycle-state"><ErrorPanel>Group creation is not available.</ErrorPanel></section>;
  }

  return <ProductPageShell className="groups-page group-lifecycle-page" eyebrow="New Group" title="Create Group">
    <GroupMetadataFormPageRegion
      mode="new"
      draft={draft}
      nameEditable
      state={mutation}
      onChange={change}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
    />
  </ProductPageShell>;
}
