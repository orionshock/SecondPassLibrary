import { createGroup } from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useBlocker, useLocation, useNavigate, useOutletContext } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { ErrorPanel, PageHeader } from "../../components/ui";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../shared/feedback/mutationState";
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
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [draft, setDraft] = useState<GroupDraft>({ ...emptyGroupDraft });
  const [baseline, setBaseline] = useState<GroupDraft>({ ...emptyGroupDraft });
  const [mutation, setMutation] = useState<MutationState>(idleMutationState);
  const allowNavigation = useRef(false);
  const dirty = !groupDraftsEqual(draft, baseline);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname
  ));
  const breadcrumbs = useMemo(() => groupNewBreadcrumbs(), []);
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
      const saved = await createGroup(createGroupInputFromDraft(draft));
      const next = groupDraftFromGroup(saved);
      setDraft(next);
      setBaseline(next);
      allowNavigation.current = true;
      navigate(groupEditPath(saved.id), {
        replace: true,
        state: groupEditNavigationState(location.state, saved, "Group created."),
      });
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (dirty && !window.confirm("Discard unsaved Group changes?")) return;
    allowNavigation.current = true;
    navigate("/groups", { state: null });
  }

  if (!canCreateGroupMetadata(currentUser)) {
    return <section className="group-lifecycle-state"><ErrorPanel>Group creation is not available.</ErrorPanel></section>;
  }

  return <div className="page-stack groups-page group-lifecycle-page">
    <PageHeader eyebrow="New Group" title="Create Group" />
    <GroupMetadataFormPageRegion
      mode="new"
      draft={draft}
      nameEditable
      state={mutation}
      onChange={change}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
    />
  </div>;
}
