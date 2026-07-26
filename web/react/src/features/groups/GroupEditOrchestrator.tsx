import {
  ApiError,
  getGroup,
  updateGroup,
  type LibraryGroup,
} from "@second-pass/spl-api";
import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link, useBlocker, useLocation, useNavigate, useOutletContext, useParams } from "react-router-dom";

import type { AppOutletContext } from "../../app/layout/AppFrame";
import { usePageBreadcrumbs } from "../../app/navigation/usePageBreadcrumbs";
import { Button, ErrorPanel, PageHeader } from "../../components/ui";
import {
  idleMutationState,
  normalizeMutationError,
  type MutationState,
} from "../../shared/feedback/mutationState";
import {
  emptyGroupDraft,
  groupDraftFromGroup,
  groupDraftsEqual,
  updateGroupInputFromDraft,
  validateGroupDraft,
  type GroupDraft,
} from "./groupDraft";
import { groupMetadataAuthority } from "./groupMetadataAuthority";
import {
  groupDetailNavigationStateFromEdit,
  groupDetailPath,
  groupEditBreadcrumbFallback,
  groupEditNavigationState,
  readGroupLifecycleSuccessMessage,
} from "./groupsBreadcrumbs";
import { GroupMetadataFormPageRegion } from "./regions/GroupMetadataFormPageRegion";
import "./Groups.css";

type GroupLoad =
  | { status: "loading" }
  | { status: "ready"; group: LibraryGroup }
  | { status: "unavailable" }
  | { status: "error"; error: Error };

export function GroupEditOrchestrator() {
  const { groupId = "" } = useParams<{ groupId: string }>();
  const { currentUser } = useOutletContext<AppOutletContext>();
  const location = useLocation();
  const navigate = useNavigate();
  const [retry, setRetry] = useState(0);
  const [load, setLoad] = useState<GroupLoad>({ status: "loading" });
  const [draft, setDraft] = useState<GroupDraft>({ ...emptyGroupDraft });
  const [baseline, setBaseline] = useState<GroupDraft>({ ...emptyGroupDraft });
  const [mutation, setMutation] = useState<MutationState>(() => ({
    ...idleMutationState,
    ...(readGroupLifecycleSuccessMessage(location.state)
      ? { message: readGroupLifecycleSuccessMessage(location.state) }
      : {}),
  }));
  const allowNavigation = useRef(false);
  const group = load.status === "ready" ? load.group : undefined;
  const dirty = !groupDraftsEqual(draft, baseline);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => (
    !allowNavigation.current && dirty && currentLocation.pathname !== nextLocation.pathname
  ));
  const breadcrumbs = useMemo(
    () => groupEditBreadcrumbFallback(groupId, group?.name),
    [group?.name, groupId],
  );
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

  useEffect(() => {
    allowNavigation.current = false;
    if (!groupId) {
      setLoad({ status: "unavailable" });
      return;
    }
    let active = true;
    setLoad({ status: "loading" });
    getGroup(groupId)
      .then((loadedGroup) => {
        if (!active) return;
        const next = groupDraftFromGroup(loadedGroup);
        setLoad({ status: "ready", group: loadedGroup });
        setDraft(next);
        setBaseline(next);
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoad(error instanceof ApiError && error.status === 404
          ? { status: "unavailable" }
          : { status: "error", error: normalizeMutationError(error) });
      });
    return () => { active = false; };
  }, [groupId, retry]);

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
      const saved = await updateGroup(groupId, updateGroupInputFromDraft(draft));
      const next = groupDraftFromGroup(saved);
      setLoad({ status: "ready", group: saved });
      setDraft(next);
      setBaseline(next);
      setMutation({ pending: false, message: "Group saved." });
      navigate(location.pathname, {
        replace: true,
        state: groupEditNavigationState(location.state, saved),
      });
    } catch (error: unknown) {
      setMutation({ pending: false, error: normalizeMutationError(error) });
    }
  }

  function cancel() {
    if (!group) return;
    if (dirty && !window.confirm("Discard unsaved Group changes?")) return;
    allowNavigation.current = true;
    navigate(groupDetailPath(group.id), {
      state: groupDetailNavigationStateFromEdit(location.state, group),
    });
  }

  if (load.status === "loading") {
    return <section className="group-lifecycle-state" aria-live="polite" aria-busy="true">Loading group...</section>;
  }
  if (load.status === "unavailable") {
    return <section className="group-lifecycle-state"><ErrorPanel>Group not found or unavailable.</ErrorPanel><Link to="/groups">Back to Groups</Link></section>;
  }
  if (load.status === "error") {
    return <section className="group-lifecycle-state"><ErrorPanel>{load.error.message}</ErrorPanel><Button type="button" onClick={() => setRetry((value) => value + 1)}>Retry</Button></section>;
  }

  const authority = groupMetadataAuthority(currentUser, load.group);
  if (authority === "none") {
    return <section className="group-lifecycle-state"><ErrorPanel>This Group is not available for metadata editing.</ErrorPanel><Link to={groupDetailPath(load.group.id)}>Back to Group</Link></section>;
  }

  return <div className="page-stack groups-page group-lifecycle-page">
    <PageHeader eyebrow="Editing Group" title={draft.name || load.group.name} />
    <GroupMetadataFormPageRegion
      mode="edit"
      draft={draft}
      nameEditable={authority === "full"}
      state={mutation}
      onChange={change}
      onSubmit={(event) => void save(event)}
      onCancel={cancel}
    />
  </div>;
}
